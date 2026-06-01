#include "logic/TCPServer.h"
#include "logic/TCPSession.h" // 需要包含TCPSession的完整定义，因为要创建它的实例
#include <chrono>
#include <sstream>
#include <thread>
#include "dpower/net/Interfaces.h"
#include "logic/utils/Logger.h"

// 引入时间处理相关的头文件
#include <iomanip>
#include <ctime>

TCPServer::TCPServer(DPower::Net::DPowerNetFactory& factory,
                     DPower::Net::DPowerIOContext& io_context,
                     std::shared_ptr<DPower::Redis::DPowerRedisClient> redis_client,
                     std::shared_ptr<SessionManager> session_manager,
                     std::shared_ptr<MultiProtocolManager> protocol_manager,
                     std::shared_ptr<PacketReassembler> packet_reassembler,
                     const std::string& stream_key,
                     const AppConfig& config)
    : factory_(factory), io_(io_context),
      m_redis_client(std::move(redis_client)),
      m_session_manager(std::move(session_manager)),
      m_protocol_manager(std::move(protocol_manager)),
      m_packet_reassembler(std::move(packet_reassembler)),
    m_stream_key(stream_key),
    license_guard_(config.max_connections),
      enable_license_check_(config.enable_license_check),
    license_watchdog_interval_seconds_(config.license_watchdog_interval_seconds)
{
    Utils::Logger::Instance().Log("INFO", "TCPServer initializing with multi-protocol support...", "TCPServer");
    if (enable_license_check_) {
        Utils::Logger::Instance().Log("INFO", "License guard enabled. Connections are controlled by LICENSE_TOKEN.", "TCPServer");
    } else {
        Utils::Logger::Instance().Log("WARN", "License guard disabled by config (enable_license_check=false).", "TCPServer");
    }
    
    // 优先使用配置文件中的端口列表
    if (!config.listen_ports.empty()) {
        Utils::Logger::Instance().Log("INFO", "Using ports from configuration file:", "TCPServer");
        for (const auto& port_config : config.listen_ports) {
            int port = port_config.first;
            const std::string& protocol_hint = port_config.second;
            Utils::Logger::Instance().Log("INFO", "Port " + std::to_string(port) + " -> " + protocol_hint, "TCPServer");
            start_listening(port);
        }
    } else {
        // 回退到从协议管理器获取端口
        Utils::Logger::Instance().Log("INFO", "No ports configured, using protocol manager ports:", "TCPServer");
        auto supported_ports = m_protocol_manager->GetSupportedPorts();
        for (int port : supported_ports) {
            Utils::Logger::Instance().Log("INFO", "Port " + std::to_string(port) + " (from protocol registry)", "TCPServer");
            start_listening(port);
        }
    }
    
    Utils::Logger::Instance().Log("INFO", "TCPServer started listening on " + std::to_string(m_acceptors.size()) + " ports", "TCPServer");
    Utils::Logger::Instance().Log(
        "INFO",
        "License watchdog interval: " + std::to_string(license_watchdog_interval_seconds_) + "s",
        "TCPServer");
    start_license_watchdog();
}

TCPServer::~TCPServer() {
    stop_license_watchdog();
}

void TCPServer::start_listening(int port) {
    try {
        auto endpoint = factory_.CreateEndpoint("0.0.0.0", port);
        auto acceptor = factory_.CreateAcceptor(io_, *endpoint);
        
        m_acceptors[port] = std::move(acceptor);
        
        Utils::Logger::Instance().Log("INFO", "Started listening on port " + std::to_string(port), "TCPServer");
        
        // 开始接受连接
        do_accept(port);
        
    } catch (const std::exception& e) {
        Utils::Logger::Instance().Log(
            "ERROR",
            "Failed to start listening on port " + std::to_string(port) + ": " + e.what(),
            "TCPServer");
    }
}

// 异步接受连接循环的实现
void TCPServer::do_accept(int port) {
    auto acceptor_it = m_acceptors.find(port);
    if (acceptor_it == m_acceptors.end()) {
        Utils::Logger::Instance().Log("ERROR", "Acceptor not found for port " + std::to_string(port), "TCPServer");
        return;
    }
    
    auto& acceptor = acceptor_it->second;
    
    acceptor->AsyncAccept([this, port](const DPower::Net::DPowerErrorCode& ec, DPower::Net::TCPSocketPtr socket) {
        if (!ec) {
            if (enable_license_check_) {
                const auto decision = license_guard_.Evaluate(m_session_manager->count());
                if (decision.disconnect_existing_connections()) {
                    handle_license_enforcement(decision);
                }

                if (decision.deny_new_connections()) {
                    const std::size_t current_sessions = m_session_manager->count();
                    std::ostringstream oss;
                    oss << "Reject new connection on port " << port
                        << ", reason=" << decision.reason
                        << ", current_sessions=" << current_sessions
                        << ", max_devices=" << decision.max_devices
                        << ", exp=" << decision.exp
                        << ", bound_mac=" << decision.mac;
                    Utils::Logger::Instance().Log("WARN", oss.str(), "LicenseGuard");
                    socket->Close();
                    do_accept(port);
                    return;
                }
            }

            socket->set_no_delay(true);
            std::make_shared<TCPSession>(io_, std::move(socket), m_redis_client, m_session_manager, m_protocol_manager, m_packet_reassembler, m_stream_key, port)->start();
        } else {
            Utils::Logger::Instance().Log(
                "ERROR",
                "Accept error on port " + std::to_string(port) + ": " + ec.Message(),
                "TCPServer");
        }

        do_accept(port);
    });
}

void TCPServer::start_license_watchdog() {
    if (!enable_license_check_) {
        return;
    }
    license_watchdog_running_.store(true);
    license_watchdog_thread_ = std::thread([this]() {
        license_watchdog_loop();
    });
}

void TCPServer::stop_license_watchdog() {
    license_watchdog_running_.store(false);
    if (license_watchdog_thread_.joinable()) {
        license_watchdog_thread_.join();
    }
}

void TCPServer::license_watchdog_loop() {
    while (license_watchdog_running_.load()) {
        const auto decision = license_guard_.Evaluate(m_session_manager->count());
        if (decision.disconnect_existing_connections()) {
            handle_license_enforcement(decision);
        }
        std::this_thread::sleep_for(std::chrono::seconds(license_watchdog_interval_seconds_));
    }
}

void TCPServer::handle_license_enforcement(const LicenseDecision& decision) {
    const std::size_t current_sessions = m_session_manager->count();
    const std::size_t closed = m_session_manager->force_close_all(decision.reason);
    
    // 将 Unix 时间戳转换为可读的字符串格式
    std::time_t exp_time = decision.exp;
    std::tm* exp_tm = std::localtime(&exp_time);
    char exp_str[32];
    std::strftime(exp_str, sizeof(exp_str), "%Y-%m-%d %H:%M:%S", exp_tm);

    if (closed > 0) {
        std::ostringstream oss;
        oss << "License validation failed (" << decision.reason << "). "
            << "Forcibly disconnected " << closed << " active session(s). "
            << "System is now rejecting new connections. "
            << "[License Details: max_devices=" << decision.max_devices
            << ", expires=" << exp_str
            << ", bound_mac=" << decision.mac << "]";
        Utils::Logger::Instance().Log("ERROR", oss.str(), "LicenseGuard");
    } else {
        std::ostringstream oss;
        oss << "License validation failed (" << decision.reason << "). "
            << "System is currently rejecting new connections. "
            << "(0 active sessions affected). "
            << "[License Details: max_devices=" << decision.max_devices
            << ", expires=" << exp_str
            << ", bound_mac=" << decision.mac << "]";
        Utils::Logger::Instance().Log("WARN", oss.str(), "LicenseGuard");
    }
}

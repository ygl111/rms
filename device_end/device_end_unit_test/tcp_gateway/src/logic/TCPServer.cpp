#include "logic/TCPServer.h"
#include "logic/TCPSession.h" // 需要包含TCPSession的完整定义，因为要创建它的实例
#include <iostream>
#include "dpower/net/Interfaces.h"

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
      m_stream_key(stream_key)
{
    std::cout << "[INFO] TCPServer initializing with multi-protocol support..." << std::endl;
    
    // 优先使用配置文件中的端口列表
    if (!config.listen_ports.empty()) {
        std::cout << "[INFO] Using ports from configuration file:" << std::endl;
        for (const auto& port_config : config.listen_ports) {
            int port = port_config.first;
            const std::string& protocol_hint = port_config.second;
            std::cout << "       Port " << port << " -> " << protocol_hint << std::endl;
            start_listening(port);
        }
    } else {
        // 回退到从协议管理器获取端口
        std::cout << "[INFO] No ports configured, using protocol manager ports:" << std::endl;
        auto supported_ports = m_protocol_manager->GetSupportedPorts();
        for (int port : supported_ports) {
            std::cout << "       Port " << port << " (from protocol registry)" << std::endl;
            start_listening(port);
        }
    }
    
    std::cout << "[INFO] TCPServer started listening on " << m_acceptors.size() << " ports" << std::endl;
}

void TCPServer::start_listening(int port) {
    try {
        auto endpoint = factory_.CreateEndpoint("0.0.0.0", port);
        auto acceptor = factory_.CreateAcceptor(io_, *endpoint);
        
        m_acceptors[port] = std::move(acceptor);
        
        std::cout << "[INFO] Started listening on port " << port << std::endl;
        
        // 开始接受连接
        do_accept(port);
        
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] Failed to start listening on port " << port << ": " << e.what() << std::endl;
    }
}

// 异步接受连接循环的实现
void TCPServer::do_accept(int port) {
    auto acceptor_it = m_acceptors.find(port);
    if (acceptor_it == m_acceptors.end()) {
        std::cerr << "[ERROR] Acceptor not found for port " << port << std::endl;
        return;
    }
    
    auto& acceptor = acceptor_it->second;
    
    acceptor->AsyncAccept([this, port](const DPower::Net::DPowerErrorCode& ec, DPower::Net::TCPSocketPtr socket) {
        if (!ec) {
            socket->set_no_delay(true);
            std::make_shared<TCPSession>(io_, std::move(socket), m_redis_client, m_session_manager, m_protocol_manager, m_packet_reassembler, m_stream_key, port)->start();
        } else {
            std::cerr << "[ERROR] Accept error on port " << port << ": " << ec.Message() << std::endl;
        }

        do_accept(port);
    });
}

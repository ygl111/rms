#pragma once // 防止头文件被重复包含

#include "dpower/net/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include <memory>
#include "logic/SessionManager.h"
#include "logic/MultiProtocolManager.h"
#include "logic/PacketReassembler.h"
#include "logic/Config.h"
#include "logic/LicenseGuard.h"
#include <atomic>
#include <thread>

// TCPServer 类，负责监听端口和接受新的TCP连接
class TCPServer {
public:
    // 构造函数
    // - io_context: Boost.Asio的核心，所有异步操作都基于它
    // - redis_client: 指向Redis客户端的唯一指针，它将被传递给每一个新的会话
    // - stream_key: Redis Stream 键名
    // - config: 应用配置，包含端口列表等信息
    TCPServer(DPower::Net::DPowerNetFactory& factory,
              DPower::Net::DPowerIOContext& io_context,
              std::shared_ptr<DPower::Redis::DPowerRedisClient> redis_client,
              std::shared_ptr<SessionManager> session_manager,
              std::shared_ptr<MultiProtocolManager> protocol_manager,
              std::shared_ptr<PacketReassembler> packet_reassembler,
              const std::string& stream_key,
              const AppConfig& config);
    ~TCPServer();

private:
    // 私有的异步接受连接函数，形成循环以持续接受新连接
    void do_accept(int port);
    
    // 启动监听指定端口
    void start_listening(int port);

    void start_license_watchdog();
    void stop_license_watchdog();
    void license_watchdog_loop();
    void handle_license_enforcement(const LicenseDecision& decision);

    // ---- 成员变量 ----

    DPower::Net::DPowerNetFactory& factory_;
    DPower::Net::DPowerIOContext&  io_;

    // 持有Redis客户端的共享指针，以便多个TCPSession可以共享
    std::shared_ptr<DPower::Redis::DPowerRedisClient> m_redis_client;

    std::shared_ptr<SessionManager> m_session_manager;
    
    // 多协议管理器
    std::shared_ptr<MultiProtocolManager> m_protocol_manager;
    
    // 分包重组器
    std::shared_ptr<PacketReassembler> m_packet_reassembler;

    // Redis Stream 键名
    std::string m_stream_key;

    LicenseGuard license_guard_;
    bool enable_license_check_ = true;
    int license_watchdog_interval_seconds_ = 1;
    std::atomic<bool> license_watchdog_running_{false};
    std::thread license_watchdog_thread_;
    
    // 多端口监听器映射
    std::map<int, std::unique_ptr<DPower::Net::DPowerTCPAcceptor>> m_acceptors;
};

#pragma once // 防止头文件被重复包含

#include "dpower/net/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include <memory>
#include <string>
#include "logic/SessionManager.h"
#include "logic/MultiProtocolManager.h"
#include "logic/PacketReassembler.h"
#include "logic/utils/Logger.h"
#include <array>
#include <deque> 
#include <mutex>
#include <atomic>

class SessionManager; // 前置声明

// 日志宏定义
#define LOG_INFO(msg) do { \
    Utils::Logger::Instance().Log("INFO", msg, "TCPSession"); \
} while(0)

#define LOG_DEBUG(msg) do { \
    Utils::Logger::Instance().Log("DEBUG", msg, "TCPSession"); \
} while(0)

#define LOG_ERROR(msg) do { \
    Utils::Logger::Instance().Log("ERROR", msg, "TCPSession"); \
} while(0)

// 简单的内存池实现，减少频繁的vector分配
class SimpleMemoryPool {
public:
    static constexpr size_t DEFAULT_BUFFER_SIZE = 8192;
    static constexpr size_t MAX_POOL_SIZE = 20;
    
    std::unique_ptr<std::vector<uint8_t>> acquire(size_t min_size = DEFAULT_BUFFER_SIZE) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        // 尝试从池中获取合适大小的缓冲区
        for (auto it = free_buffers_.begin(); it != free_buffers_.end(); ++it) {
            if ((*it)->capacity() >= min_size) {
                auto buffer = std::move(*it);
                free_buffers_.erase(it);
                buffer->clear();
                return buffer;
            }
        }
        
        // 池中没有合适的，创建新的
        auto buffer = std::make_unique<std::vector<uint8_t>>();
        buffer->reserve(std::max(min_size, DEFAULT_BUFFER_SIZE));
        return buffer;
    }
    
    void release(std::unique_ptr<std::vector<uint8_t>> buffer) {
        if (!buffer || buffer->capacity() > DEFAULT_BUFFER_SIZE * 4) {
            return; // 丢弃过大的缓冲区
        }
        
        std::lock_guard<std::mutex> lock(mutex_);
        if (free_buffers_.size() < MAX_POOL_SIZE) {
            buffer->clear();
            free_buffers_.emplace_back(std::move(buffer));
        }
    }
    
private:
    std::mutex mutex_;
    std::vector<std::unique_ptr<std::vector<uint8_t>>> free_buffers_;
};

// TCPSession 类负责处理单个TCP连接的所有逻辑
// 它继承自 std::enable_shared_from_this 以便在异步操作中安全地管理自身生命周期
class TCPSession : public std::enable_shared_from_this<TCPSession> {
public:
    // 构造函数，接收一个已连接的socket和Redis客户端的共享指针
    TCPSession(DPower::Net::DPowerIOContext& io_context,
               std::unique_ptr<DPower::Net::DPowerTCPSocket> socket,
               std::shared_ptr<DPower::Redis::DPowerRedisClient> redis_client,
               std::shared_ptr<SessionManager> session_manager,
               std::shared_ptr<MultiProtocolManager> protocol_manager,
               std::shared_ptr<PacketReassembler> packet_reassembler,
               const std::string& stream_key,
               int port); // 添加端口参数

    // 启动会话的入口函数
    void start();
    void write_response(std::shared_ptr<std::vector<uint8_t>> response_data);
    void ForceClose(const std::string& reason);

private:
    // 私有的异步读取函数，形成循环以持续接收数据
    void do_read();
    // 串行写入函数声明
    void do_write();
    // 将断开逻辑提取为独立函数
    void handle_disconnect(const DPower::Net::DPowerErrorCode& ec);
    
    // 协议识别和消息处理
    void process_protocol_message(const std::vector<uint8_t>& data);
    void send_to_parser(const ProtocolIdentificationResult& result, std::unique_ptr<std::vector<uint8_t>> message_buffer);

    // ---- 成员变量 ----
    
    //保存 io_context 的引用
    DPower::Net::DPowerIOContext& m_io_context;
    // Boost.Asio的socket对象，代表与客户端的连接
    std::unique_ptr<DPower::Net::DPowerTCPSocket> socket_;

    // 保存客户端的IP和端口信息，用于日志记录
    std::string client_info_;

    // 指向Redis客户端的共享指针，用于将数据推送到Redis
    std::shared_ptr<DPower::Redis::DPowerRedisClient> m_redis_client;

    // 增加成员
    std::shared_ptr<SessionManager> m_session_manager;
    
    // 多协议管理器
    std::shared_ptr<MultiProtocolManager> m_protocol_manager;
    
    // 分包重组器
    std::shared_ptr<PacketReassembler> m_packet_reassembler;
    
    // 当前会话的端口
    int m_port;

    // Redis Stream 键名
    std::string m_stream_key;

    // 数据接收缓冲区 - 优化的循环缓冲区管理
    std::array<uint8_t, 8192> m_temp_buffer;
    std::vector<uint8_t> m_read_buffer;
    size_t m_read_pos = 0; // 已读取位置
    static constexpr size_t SHRINK_THRESHOLD = 16384; // 缓冲区收缩阈值
    
    void optimize_read_buffer(); // 优化缓冲区布局
    
    // 写入队列，确保异步写入是串行的
    std::deque<std::shared_ptr<std::vector<uint8_t>>> m_write_queue;
    bool m_is_writing = false;
    
    // 内存池，减少频繁的内存分配
    static SimpleMemoryPool s_memory_pool;

    // 防止重复断开导致重复清理
    std::atomic<bool> is_closed_{false};
};

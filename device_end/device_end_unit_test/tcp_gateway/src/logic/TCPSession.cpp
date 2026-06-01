#include "logic/TCPSession.h"
#include "logic/SessionManager.h"
#include "logic/ThreadPool.h"
#include <iostream>
#include <chrono>
#include <unordered_map>
#include <string>
#include <vector>

#include "dpower/utils/Base64.h"
#include "dpower/net/Interfaces.h"

// 假设 g_thread_pool 是全局可访问的
extern ThreadPool g_thread_pool;

// 静态内存池定义
SimpleMemoryPool TCPSession::s_memory_pool;

TCPSession::TCPSession(DPower::Net::DPowerIOContext& io_context,
                       std::unique_ptr<DPower::Net::DPowerTCPSocket> socket,
                       std::shared_ptr<DPower::Redis::DPowerRedisClient> redis_client,
                       std::shared_ptr<SessionManager> session_manager,
                       std::shared_ptr<MultiProtocolManager> protocol_manager,
                       std::shared_ptr<PacketReassembler> packet_reassembler,
                       const std::string& stream_key,
                       int port)
    : m_io_context(io_context),
      socket_(std::move(socket)),
      m_redis_client(std::move(redis_client)),
      m_session_manager(std::move(session_manager)),
      m_protocol_manager(std::move(protocol_manager)),
      m_packet_reassembler(std::move(packet_reassembler)),
      m_port(port),
      m_stream_key(stream_key)
{
    m_read_buffer.reserve(8192);
}

void TCPSession::start() {
    try {
        client_info_ = socket_->RemoteAddress() + ":" + std::to_string(socket_->RemotePort());
        LOG_INFO(">>> Client connected: " + client_info_ + " on port " + std::to_string(m_port));
        m_session_manager->add(client_info_, shared_from_this());
    } catch (const std::exception& e) {
        LOG_ERROR(">>> Failed to get client info: " + std::string(e.what()));
        return;
    }
    do_read();
}

// 采用标准的异步读取模式
void TCPSession::do_read() {
    auto self = shared_from_this();
    socket_->AsyncReadSome(DPower::Net::MakeMutableBuffer(m_temp_buffer.data(), m_temp_buffer.size()),
        [this, self](const DPower::Net::DPowerErrorCode& ec, std::size_t length) {
            if (!ec) {
                // 1. 追加新数据到主缓冲区
                m_read_buffer.insert(m_read_buffer.end(), m_temp_buffer.data(), m_temp_buffer.data() + length);
                
                // 2. 在当前回调中，循环处理所有可能存在的完整报文
                process_protocol_message(m_read_buffer);
                
                // 3. 继续读取
                do_read();
            } else {
                handle_disconnect(ec);
            }
        });
}

void TCPSession::process_protocol_message(const std::vector<uint8_t>& /*data*/) {
    // 改进说明:
    // 1. 循环扫描多个潜在头, 处理粘包/伪头
    // 2. 伪头判定: 无效长度(0 / <header / >MAX / 过小剩余) 时跳过并继续搜索下一处 55 55 03
    // 3. 加入最大逻辑长度上限与缓冲硬截断
    // 4. 节流日志: 对重复伪头不刷屏

    static const size_t kHardBufferLimit = 512 * 1024;      // 内存保护上限
    static const size_t kMaxLogicalMessageLength = 128 * 1024; // 单报文逻辑上限 (可后续配置)
    static const size_t kHeaderSizeV1 = 34; // dp_protocol_v1 header_size

    // 节流状态(静态, 针对所有 session 可按需改成成员变量)
    static std::chrono::steady_clock::time_point s_last_fail_log_time = std::chrono::steady_clock::now();
    static size_t s_last_fail_size = 0;

    auto now = std::chrono::steady_clock::now();

    // 过大缓冲截断
    if (m_read_buffer.size() > kHardBufferLimit) {
        LOG_INFO("[WARN] Read buffer exceeded " + std::to_string(kHardBufferLimit) + 
                " bytes on port " + std::to_string(m_port) + ", dropping old data (" + 
                std::to_string(m_read_buffer.size()) + ")");
        if (m_read_buffer.size() > 128) { // 留更长尾巴试图保持下一个头
            std::vector<uint8_t> tail(m_read_buffer.end() - 128, m_read_buffer.end());
            m_read_buffer.swap(tail);
        }
    }

    bool progress = true; // 控制循环避免空转
    int safety_loop_guard = 0;
    while (progress && !m_read_buffer.empty() && safety_loop_guard < 1024) {
        progress = false;
        ++safety_loop_guard;

        // 寻找头 55 55 03
        size_t pos = 0;
        while (pos + 2 < m_read_buffer.size()) {
            if (m_read_buffer[pos] == 0x55 && m_read_buffer[pos + 1] == 0x55 && m_read_buffer[pos + 2] == 0x03) {
                break;
            }
            ++pos;
        }

        if (pos + 2 >= m_read_buffer.size()) {
            // 未找到头, 丢弃全部(也可保留少量尾部). 这里保留最后 2 字节避免跨块匹配丢失
            if (m_read_buffer.size() > 2) {
                std::vector<uint8_t> tail(m_read_buffer.end() - 2, m_read_buffer.end());
                m_read_buffer.swap(tail);
            }
            break; // 等待更多数据
        }

        if (pos > 0) {
            // 丢弃头前垃圾
            m_read_buffer.erase(m_read_buffer.begin(), m_read_buffer.begin() + pos);
            LOG_DEBUG("[DEBUG][ALIGN] Discarded " + std::to_string(pos) + 
                     " stray bytes before header on port " + std::to_string(m_port));
        }

        // 需要至少 header 大小
        if (m_read_buffer.size() < kHeaderSizeV1) {
            // 等更多数据
            break;
        }

        // 尝试用协议管理器识别(已按端口放宽签名)
        auto result = m_protocol_manager->IdentifyProtocol(m_read_buffer, m_port);

        if (!result.is_valid) {
            // 进一步基于长度字段做伪头判定:
            bool pseudo_header = false;
            std::string reason;

            // 手动再提取长度字段 (偏移3, size2 小端) 以便给出更明确日志
            if (m_read_buffer.size() >= kHeaderSizeV1) {
                size_t body_len = 0;
                body_len |= static_cast<size_t>(m_read_buffer[3]) | (static_cast<size_t>(m_read_buffer[4]) << 8);
                size_t total_len = kHeaderSizeV1 + body_len + 2 /*CRC*/ + 2 /*tail*/;
                if (body_len == 0) { pseudo_header = true; reason = "zero_length"; }
                else if (total_len < kHeaderSizeV1) { pseudo_header = true; reason = "total_less_than_header"; }
                else if (total_len > kMaxLogicalMessageLength) { pseudo_header = true; reason = "exceed_max_limit"; }
                else if (total_len > m_read_buffer.size()) {
                    // 长度看似合法但数据不够, 这其实属于不完整, 不判伪头
                    // 等待更多数据, 不打印失败日志
                    // 为避免卡死在伪头: 若 body_len 非常大(比如 >64K) 仍认为伪头
                    if (total_len > 64 * 1024) { pseudo_header = true; reason = "suspect_oversize_wait"; }
                    else {
                        // 不完整, 退出等待更多数据
                        break;
                    }
                } else {
                    // total_len <= buffer.size() 但 is_valid=false -> 极可能签名或其它校验失败, 视为伪头
                    pseudo_header = true; reason = "invalid_structure";
                }
            }

            if (pseudo_header) {
                uint8_t b0 = m_read_buffer[0];
                uint8_t b1 = m_read_buffer[1];
                uint8_t b2 = m_read_buffer[2];
                // 节流: 仅在 500ms 间隔或 size 跨阈值时打印
                bool should_log = false;
                auto ms_since = std::chrono::duration_cast<std::chrono::milliseconds>(now - s_last_fail_log_time).count();
                if (ms_since > 500 || m_read_buffer.size() / 4096 != s_last_fail_size / 4096) {
                    should_log = true;
                }
                if (should_log) {
                    LOG_DEBUG("[DEBUG][PSEUDO] Skip pseudo-header (" + 
                             std::to_string((int)b0) + " " + std::to_string((int)b1) + " " + std::to_string((int)b2) +
                             ") reason=" + reason + ", buffer_size=" + std::to_string(m_read_buffer.size()) + 
                             " port=" + std::to_string(m_port));
                    s_last_fail_log_time = now;
                    s_last_fail_size = m_read_buffer.size();
                }
                // 跳过首字节继续找下一个头
                m_read_buffer.erase(m_read_buffer.begin());
                progress = true;
                continue;
            } else {
                // 不完整, 退出等待更多数据
                break;
            }
        }

        // 拿到合法 result (is_valid)
        if (result.message_length == 0 || result.message_length > kMaxLogicalMessageLength) {
            // 防御性: 认为伪头
            LOG_DEBUG("[DEBUG][GUARD] Discard header due to absurd length=" + 
                     std::to_string(result.message_length) + " size=" + std::to_string(m_read_buffer.size()) + 
                     " port=" + std::to_string(m_port));
            m_read_buffer.erase(m_read_buffer.begin());
            progress = true;
            continue;
        }

        if (m_read_buffer.size() < result.message_length) {
            // 数据还不够, 等待更多块
            // 可以输出一次不完整日志(节流), 这里简化
            break;
        }

        // 完整报文 - 使用内存池优化
        auto full_message_buffer = s_memory_pool.acquire(result.message_length);
        full_message_buffer->assign(m_read_buffer.begin(), m_read_buffer.begin() + result.message_length);
        
        LOG_DEBUG("[DEBUG] Protocol identified: " + result.protocol_name + " v" + result.version +
                 " (ID: " + result.protocol_id + ") on port " + std::to_string(m_port) +
                 ", message length: " + std::to_string(result.message_length));

        // 处理消息并归还缓冲区
        std::vector<uint8_t> processed_message = m_packet_reassembler->ProcessMessage(*full_message_buffer, client_info_);
        if (!processed_message.empty()) {
            // 将处理后的消息复制到新的缓冲区并直接发送
            auto processed_buffer = s_memory_pool.acquire(processed_message.size());
            processed_buffer->assign(processed_message.begin(), processed_message.end());
            send_to_parser(result, std::move(processed_buffer));
        } else {
            LOG_DEBUG("[DEBUG] Message is part of multi-packet sequence, waiting for reassembly completion");
        }
        
        // 归还原始消息缓冲区
        s_memory_pool.release(std::move(full_message_buffer));
        
        m_read_buffer.erase(m_read_buffer.begin(), m_read_buffer.begin() + result.message_length);
        progress = true; // 继续循环处理剩余粘包
    }
    
    // 定期优化缓冲区布局
    optimize_read_buffer();
}

void TCPSession::optimize_read_buffer() {
    // 如果已读取的数据超过阈值，移动未读数据到缓冲区开头
    if (m_read_pos > SHRINK_THRESHOLD && m_read_pos < m_read_buffer.size()) {
        size_t unread_size = m_read_buffer.size() - m_read_pos;
        std::memmove(m_read_buffer.data(), m_read_buffer.data() + m_read_pos, unread_size);
        m_read_buffer.resize(unread_size);
        m_read_pos = 0;
    }
    // 如果缓冲区过大且大部分为空，适当收缩
    else if (m_read_buffer.capacity() > 64 * 1024 && m_read_buffer.size() < m_read_buffer.capacity() / 4) {
        std::vector<uint8_t> optimized_buffer;
        optimized_buffer.reserve(std::max(static_cast<size_t>(8192), m_read_buffer.size() * 2));
        optimized_buffer.assign(m_read_buffer.begin(), m_read_buffer.end());
        m_read_buffer.swap(optimized_buffer);
    }
}

void TCPSession::send_to_parser(const ProtocolIdentificationResult& result, std::unique_ptr<std::vector<uint8_t>> message_buffer) {
    // 检查线程池队列状态，避免无限排队
    if (g_thread_pool.queue_size() > 5000) { // 队列过长时直接丢弃
        LOG_ERROR("Thread pool queue overloaded (" + std::to_string(g_thread_pool.queue_size()) + 
                 "), dropping message from " + client_info_);
        s_memory_pool.release(std::move(message_buffer));
        return;
    }
    
    // 投递到线程池处理，传递智能指针避免数据拷贝
    bool enqueued = g_thread_pool.post([redis_client = m_redis_client,
                        message_buffer = std::shared_ptr<std::vector<uint8_t>>(message_buffer.release()),
                        client_info = client_info_,
                        stream_key = m_stream_key,
                        protocol_result = result]() mutable {
        
        // 构建Redis Stream数据
        std::map<std::string, std::string> stream_data;
        
        // 使用更高效的时间戳获取
        auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        
        stream_data["timestamp_ms"] = std::to_string(now_ms);
        stream_data["source_ip"] = client_info;
        stream_data["raw_data_base64"] = DPower::Utils::DPowerBase64::Encode(
            message_buffer->data(), message_buffer->size());
        stream_data["protocol_id"] = protocol_result.protocol_id;
        stream_data["protocol_name"] = protocol_result.protocol_name;
        stream_data["protocol_version"] = protocol_result.version;
        stream_data["message_length"] = std::to_string(protocol_result.message_length);
        stream_data["header_size"] = std::to_string(protocol_result.header_size);
        stream_data["body_size"] = std::to_string(protocol_result.body_size);
        
        auto stream_result = redis_client->StreamAdd(stream_key, stream_data);
        if (stream_result.success) {
            LOG_INFO("Pushed " + std::to_string(message_buffer->size()) + " bytes from " + client_info +
                    " (Protocol: " + protocol_result.protocol_name + " v" + protocol_result.version + ")" +
                    " to Redis Stream '" + stream_key + "'. Message ID: " + stream_result.data);
        } else {
            LOG_ERROR("!!! Failed to push message to Redis from " + client_info + 
                     " to Redis Stream '" + stream_key + "': " + stream_result.error_message);
        }
        
        // 注意：使用shared_ptr，内存会自动释放
    });
    
    if (!enqueued) {
        LOG_ERROR("Failed to enqueue Redis task for " + client_info_ + ", queue full or stopped");
        s_memory_pool.release(std::move(message_buffer));
    }
}

void TCPSession::write_response(std::shared_ptr<std::vector<uint8_t>> response_data) {
    m_write_queue.push_back(response_data);
    
    if (!m_is_writing) {
        do_write();
    }
}

void TCPSession::do_write() {
    if (m_write_queue.empty()) {
        m_is_writing = false;
        return;
    }
    
    m_is_writing = true;
    auto response_data = m_write_queue.front();
    m_write_queue.pop_front();
    
    auto self = shared_from_this();
    socket_->AsyncWrite(response_data->data(), response_data->size(),
        [this, self, response_data](const DPower::Net::DPowerErrorCode& ec, std::size_t length) {
            if (!ec) {
                LOG_INFO("[RESPONSE] Sent " + std::to_string(length) + " bytes to " + client_info_);
                do_write(); // 继续处理队列中的下一个响应
            } else {
                LOG_ERROR("[ERROR] Write error: " + ec.Message());
                handle_disconnect(ec);
            }
        });
}

void TCPSession::handle_disconnect(const DPower::Net::DPowerErrorCode& ec) {
    LOG_INFO(">>> Client disconnected: " + client_info_ + " (Error: " + ec.Message() + ")");
    m_session_manager->remove(client_info_);
}


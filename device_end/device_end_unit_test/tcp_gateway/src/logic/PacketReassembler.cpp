#include "logic/PacketReassembler.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <algorithm>

// CRC16查找表 - 与设备端保持一致
static const uint16_t crc16_table[256] = {
    0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
    0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
    0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
    0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
    0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
    0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
    0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
    0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
    0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
    0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
    0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
    0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
    0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
    0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
    0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
    0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
    0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
    0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
    0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
    0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
    0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
    0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
    0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
    0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
    0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
    0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
    0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
    0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
    0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
};

PacketReassembler::PacketReassembler(int timeout_seconds)
    : timeout_seconds_(timeout_seconds),
      total_messages_processed_(0),
      single_packet_messages_(0),
      multi_packet_messages_(0),
      successful_reassemblies_(0),
      timeout_sessions_(0),
      error_packets_(0) {
    std::cout << "[PacketReassembler] Initialized with timeout: " << timeout_seconds << " seconds" << std::endl;
}

PacketReassembler::~PacketReassembler() {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    std::cout << "[PacketReassembler] Shutting down. Active sessions: " << sessions_.size() << std::endl;
}

std::vector<uint8_t> PacketReassembler::ProcessMessage(const std::vector<uint8_t>& message_data, 
                                                      const std::string& client_info) {
    {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        total_messages_processed_++;
    }
    
    // 1. 检查是否是点钞上报消息
    if (!IsBanknoteReportMessage(message_data)) {
        // 非点钞消息，直接返回原始数据
        return message_data;
    }
    
    // 2. 提取分包信息
    PacketType packet_type = ExtractPacketType(message_data);
    
    // 3. 单包消息，直接返回
    if (packet_type == PacketType::SINGLE) {
        std::lock_guard<std::mutex> lock(stats_mutex_);
        single_packet_messages_++;
        std::cout << "[PacketReassembler] Single packet message from " << client_info << std::endl;
        return message_data;
    }
    
    // 4. 多包消息处理
    std::string device_id = ExtractDeviceId(message_data);
    uint16_t seq_num = ExtractSequenceNumber(message_data);
    
    std::cout << "[PacketReassembler] Multi-packet message from " << client_info 
              << ", device: " << device_id 
              << ", seq: " << seq_num 
              << ", type: " << static_cast<int>(packet_type) << std::endl;
    
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    
    // 5. 获取或创建重组会话
    // 对于多包消息，使用设备ID作为会话键，因为设备端每个分包有不同的序列号
    std::string session_key;
    std::shared_ptr<ReassemblySession> session;
    
    if (packet_type == PacketType::FIRST) {
        // 首包：创建新会话，使用设备ID作为会话键
        session_key = device_id + "_multipacket";
        
        // 如果已经存在会话，清理旧会话（可能是之前超时的）
        auto existing_it = sessions_.find(session_key);
        if (existing_it != sessions_.end()) {
            std::cout << "[PacketReassembler] Cleaning up existing session for device: " << device_id << std::endl;
            sessions_.erase(existing_it);
        }
        
        session = std::make_shared<ReassemblySession>(device_id, seq_num);
        sessions_[session_key] = session;
        
        std::lock_guard<std::mutex> stats_lock(stats_mutex_);
        multi_packet_messages_++;
    } else {
        // 非首包：查找现有会话
        session_key = device_id + "_multipacket";
        auto session_it = sessions_.find(session_key);
        if (session_it == sessions_.end()) {
            std::cerr << "[PacketReassembler] ERROR: Received non-first packet without existing session: " 
                      << session_key << " (seq: " << seq_num << ")" << std::endl;
            std::lock_guard<std::mutex> stats_lock(stats_mutex_);
            error_packets_++;
            return {};  // 返回空数据，表示处理失败
        }
        session = session_it->second;
    }
    
    // 6. 将分包添加到会话中
    // 去除消息的头部和尾部，只保留消息体部分
    size_t body_start = HEADER_SIZE;
    size_t body_end = message_data.size() - CRC_SIZE - TAIL_SIZE;
    
    if (body_end <= body_start) {
        std::cerr << "[PacketReassembler] ERROR: Invalid message size for session: " 
                  << session_key << std::endl;
        sessions_.erase(sessions_.find(session_key));
        std::lock_guard<std::mutex> stats_lock(stats_mutex_);
        error_packets_++;
        return {};
    }
    
    std::vector<uint8_t> packet_body(message_data.begin() + body_start, 
                                    message_data.begin() + body_end);
    
    auto packet_info = std::make_shared<PacketInfo>(packet_type, std::move(packet_body));
    session->packets.push_back(packet_info);
    
    // 7. 检查是否重组完成
    if (packet_type == PacketType::LAST) {
        session->is_complete = true;
        
        // 验证分包序列的完整性
        std::vector<PacketType> expected_sequence;
        if (session->packets.size() == 2) {
            expected_sequence = {PacketType::FIRST, PacketType::LAST};
        } else if (session->packets.size() > 2) {
            expected_sequence.push_back(PacketType::FIRST);
            for (size_t i = 1; i < session->packets.size() - 1; ++i) {
                expected_sequence.push_back(PacketType::MIDDLE);
            }
            expected_sequence.push_back(PacketType::LAST);
        } else {
            std::cerr << "[PacketReassembler] ERROR: Invalid packet sequence length: " 
                      << session->packets.size() << " for session: " << session_key << std::endl;
            sessions_.erase(sessions_.find(session_key));
            std::lock_guard<std::mutex> stats_lock(stats_mutex_);
            error_packets_++;
            return {};
        }
        
        // 验证序列
        bool sequence_valid = true;
        if (session->packets.size() != expected_sequence.size()) {
            sequence_valid = false;
        } else {
            for (size_t i = 0; i < session->packets.size(); ++i) {
                if (session->packets[i]->packet_type != expected_sequence[i]) {
                    sequence_valid = false;
                    break;
                }
            }
        }
        
        if (!sequence_valid) {
            std::cerr << "[PacketReassembler] ERROR: Invalid packet sequence for session: " 
                      << session_key << std::endl;
            sessions_.erase(sessions_.find(session_key));
            std::lock_guard<std::mutex> stats_lock(stats_mutex_);
            error_packets_++;
            return {};
        }
        
        // 重组消息
        std::vector<uint8_t> reassembled_message = ReassembleMessage(session);
        sessions_.erase(sessions_.find(session_key));
        
        {
            std::lock_guard<std::mutex> stats_lock(stats_mutex_);
            successful_reassemblies_++;
        }
        
        std::cout << "[PacketReassembler] Successfully reassembled message for session: " 
                  << session_key << ", total size: " << reassembled_message.size() << " bytes" << std::endl;
        
        return reassembled_message;
    }
    
    // 8. 重组未完成，返回空数据表示等待更多分包
    std::cout << "[PacketReassembler] Waiting for more packets for session: " 
              << session_key << " (" << session->packets.size() << " packets received)" << std::endl;
    return {};
}

bool PacketReassembler::IsBanknoteReportMessage(const std::vector<uint8_t>& message_data) const {
    if (message_data.size() < HEADER_SIZE) {
        return false;
    }
    
    uint16_t msg_id = ExtractMessageId(message_data);
    return msg_id == MSG_ID_BANKNOTE_REPORT;
}

PacketType PacketReassembler::ExtractPacketType(const std::vector<uint8_t>& message_data) const {
    if (message_data.size() <= PACKET_TYPE_OFFSET) {
        return PacketType::SINGLE;
    }
    
    uint8_t packet_flag = message_data[PACKET_TYPE_OFFSET];
    return static_cast<PacketType>(packet_flag);
}

std::string PacketReassembler::ExtractDeviceId(const std::vector<uint8_t>& message_data) const {
    if (message_data.size() < DEVICE_ID_OFFSET + DEVICE_ID_SIZE) {
        return "";
    }
    
    std::stringstream ss;
    ss << std::hex << std::uppercase;
    for (size_t i = 0; i < DEVICE_ID_SIZE; ++i) {
        ss << std::setw(2) << std::setfill('0') 
           << static_cast<int>(message_data[DEVICE_ID_OFFSET + i]);
    }
    return ss.str();
}

uint16_t PacketReassembler::ExtractSequenceNumber(const std::vector<uint8_t>& message_data) const {
    if (message_data.size() < SEQ_NUM_OFFSET + 2) {
        return 0;
    }
    
    // 小端序
    return message_data[SEQ_NUM_OFFSET] | 
           (static_cast<uint16_t>(message_data[SEQ_NUM_OFFSET + 1]) << 8);
}

uint16_t PacketReassembler::ExtractMessageId(const std::vector<uint8_t>& message_data) const {
    if (message_data.size() < MSG_ID_OFFSET + 2) {
        return 0;
    }
    
    // 小端序
    return message_data[MSG_ID_OFFSET] | 
           (static_cast<uint16_t>(message_data[MSG_ID_OFFSET + 1]) << 8);
}

std::string PacketReassembler::GenerateSessionKey(const std::string& device_id, 
                                                 uint16_t sequence_number) const {
    std::stringstream ss;
    ss << device_id << "_" << sequence_number;
    return ss.str();
}

std::vector<uint8_t> PacketReassembler::ReassembleMessage(
    const std::shared_ptr<ReassemblySession>& session) const {
    
    // 1. 计算重组后的消息体总长度
    size_t total_body_length = 0;
    bool is_first_packet = true;
    for (const auto& packet : session->packets) {
        if (is_first_packet) {
            // 首包：包含完整数据
            total_body_length += packet->data.size();
            is_first_packet = false;
        } else {
            // 非首包：跳过前2个字节（infoType和subpackFlag）
            if (packet->data.size() > 2) {
                total_body_length += packet->data.size() - 2;
            }
        }
    }
    
    // 2. 构建完整消息
    std::vector<uint8_t> reassembled_message;
    reassembled_message.reserve(HEADER_SIZE + total_body_length + CRC_SIZE + TAIL_SIZE);
    
    // 3. 复制首包的头部信息 (从第一个包的原始消息中提取)
    // 注意：这里需要从会话中保存的原始首包消息中提取头部
    // 为简化，我们重新构造头部（在实际实现中应该保存原始头部）
    
    // 构造消息头（基于DP协议v1格式）
    reassembled_message.resize(HEADER_SIZE);
    
    // msg_head (0x5555)
    reassembled_message[0] = 0x55;
    reassembled_message[1] = 0x55;
    
    // msg_type (0x03)
    reassembled_message[2] = 0x03;
    
    // msg_body_len (小端序，稍后更新)
    reassembled_message[3] = total_body_length & 0xFF;
    reassembled_message[4] = (total_body_length >> 8) & 0xFF;
    
    // msg_attribute (从首包推断，通常为0x01)
    reassembled_message[5] = 0x01;
    
    // msg_id (12, 小端序)
    reassembled_message[6] = MSG_ID_BANKNOTE_REPORT & 0xFF;
    reassembled_message[7] = (MSG_ID_BANKNOTE_REPORT >> 8) & 0xFF;
    
    // device_id (从会话信息中提取，转换回二进制)
    for (size_t i = 0; i < DEVICE_ID_SIZE; ++i) {
        std::string hex_byte = session->device_id.substr(i * 2, 2);
        reassembled_message[8 + i] = static_cast<uint8_t>(std::stoi(hex_byte, nullptr, 16));
    }
    
    // seq_num (小端序)
    reassembled_message[32] = session->sequence_number & 0xFF;
    reassembled_message[33] = (session->sequence_number >> 8) & 0xFF;
    
    // 4. 重组消息体
    is_first_packet = true;  // 重置标志
    for (const auto& packet : session->packets) {
        if (is_first_packet) {
            // 首包：包含完整数据（包括infoType和subpackFlag）
            reassembled_message.insert(reassembled_message.end(), 
                                      packet->data.begin(), packet->data.end());
            is_first_packet = false;
        } else {
            // 非首包：跳过前2个字节（infoType和subpackFlag），只取实际数据
            if (packet->data.size() > 2) {
                reassembled_message.insert(reassembled_message.end(), 
                                          packet->data.begin() + 2, packet->data.end());
            }
        }
    }
    
    // 5. 计算并添加CRC16
    uint16_t crc = CalculateCRC16(reassembled_message);
    reassembled_message.push_back(crc & 0xFF);           // CRC低字节
    reassembled_message.push_back((crc >> 8) & 0xFF);    // CRC高字节
    
    // 6. 添加消息尾 (0xAAAA)
    reassembled_message.push_back(0xAA);
    reassembled_message.push_back(0xAA);
    
    return reassembled_message;
}

uint16_t PacketReassembler::CalculateCRC16(const std::vector<uint8_t>& message_data) const {
    uint16_t crc_reg = 0xFFFF;
    for (uint8_t byte : message_data) {
        crc_reg = (crc_reg >> 8) ^ crc16_table[(crc_reg ^ byte) & 0xff];
    }
    return (~crc_reg) & 0x0000FFFF;
}

void PacketReassembler::UpdateMessageLength(std::vector<uint8_t>& message_data, 
                                          uint16_t new_body_length) const {
    if (message_data.size() >= BODY_LENGTH_OFFSET + 2) {
        message_data[BODY_LENGTH_OFFSET] = new_body_length & 0xFF;
        message_data[BODY_LENGTH_OFFSET + 1] = (new_body_length >> 8) & 0xFF;
    }
}

void PacketReassembler::CleanupExpiredSessions() {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    auto now = std::chrono::system_clock::now();
    auto timeout_duration = std::chrono::seconds(timeout_seconds_);
    
    auto it = sessions_.begin();
    size_t removed_count = 0;
    
    while (it != sessions_.end()) {
        if (now - it->second->start_time > timeout_duration) {
            std::cout << "[PacketReassembler] Cleaning up expired session: " << it->first << std::endl;
            it = sessions_.erase(it);
            removed_count++;
        } else {
            ++it;
        }
    }
    
    if (removed_count > 0) {
        std::lock_guard<std::mutex> stats_lock(stats_mutex_);
        timeout_sessions_ += removed_count;
        std::cout << "[PacketReassembler] Cleaned up " << removed_count << " expired sessions" << std::endl;
    }
}

size_t PacketReassembler::GetActiveSessionCount() const {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    return sessions_.size();
}

std::map<std::string, uint64_t> PacketReassembler::GetStatistics() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    return {
        {"total_messages_processed", total_messages_processed_},
        {"single_packet_messages", single_packet_messages_},
        {"multi_packet_messages", multi_packet_messages_},
        {"successful_reassemblies", successful_reassemblies_},
        {"timeout_sessions", timeout_sessions_},
        {"error_packets", error_packets_},
        {"active_sessions", GetActiveSessionCount()}
    };
}
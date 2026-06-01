#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <chrono>
#include <mutex>

/**
 * @brief 分包重组器 - 处理设备端点钞信息分包重组
 * 
 * 设备端分包机制:
 * - 每包最多200张点钞记录
 * - 分包标识: 0x00(不分包), 0x01(首包), 0x02(中间包), 0x03(尾包)
 * - 首包包含RMS_NoteInfoPrefix12头部信息和货币统计
 * - 消息ID: 12 (ID_UPLOAD_COUNT_BILL)
 */

enum class PacketType : uint8_t {
    SINGLE = 0x00,    // 不分包
    FIRST = 0x01,     // 首包
    MIDDLE = 0x02,    // 中间包
    LAST = 0x03       // 尾包
};

struct PacketInfo {
    PacketType packet_type;           // 分包类型
    std::vector<uint8_t> data;        // 包数据(去除分包标识后)
    std::chrono::system_clock::time_point timestamp; // 接收时间
    
    PacketInfo(PacketType type, std::vector<uint8_t> packet_data)
        : packet_type(type), data(std::move(packet_data)), 
          timestamp(std::chrono::system_clock::now()) {}
};

struct ReassemblySession {
    std::string device_id;                            // 设备ID (24字节)
    uint16_t sequence_number;                         // 序列号
    std::vector<std::shared_ptr<PacketInfo>> packets; // 分包列表
    std::chrono::system_clock::time_point start_time; // 会话开始时间
    bool is_complete;                                 // 是否已完成重组
    
    ReassemblySession(const std::string& dev_id, uint16_t seq_num)
        : device_id(dev_id), sequence_number(seq_num), 
          start_time(std::chrono::system_clock::now()), is_complete(false) {}
};

class PacketReassembler {
public:
    /**
     * @brief 构造函数
     * @param timeout_seconds 分包重组超时时间(秒)，默认30秒
     */
    explicit PacketReassembler(int timeout_seconds = 30);
    
    /**
     * @brief 析构函数
     */
    ~PacketReassembler();
    
    /**
     * @brief 处理接收到的消息，判断是否需要分包重组
     * @param message_data 完整的协议消息数据
     * @param client_info 客户端信息
     * @return 如果返回数据，说明重组完成；如果为空，说明仍在等待后续分包
     */
    std::vector<uint8_t> ProcessMessage(const std::vector<uint8_t>& message_data, 
                                       const std::string& client_info);
    
    /**
     * @brief 检查是否是点钞上报消息(msg_id = 12)
     * @param message_data 消息数据
     * @return true if 是点钞上报消息
     */
    bool IsBanknoteReportMessage(const std::vector<uint8_t>& message_data) const;
    
    /**
     * @brief 从消息中提取分包标识
     * @param message_data 消息数据
     * @return 分包类型，如果不是分包消息返回SINGLE
     */
    PacketType ExtractPacketType(const std::vector<uint8_t>& message_data) const;
    
    /**
     * @brief 清理超时的重组会话
     */
    void CleanupExpiredSessions();
    
    /**
     * @brief 获取当前活跃的重组会话数量
     * @return 活跃会话数
     */
    size_t GetActiveSessionCount() const;
    
    /**
     * @brief 获取统计信息
     * @return 统计信息映射
     */
    std::map<std::string, uint64_t> GetStatistics() const;

private:
    /**
     * @brief 从消息中提取设备ID
     * @param message_data 消息数据
     * @return 设备ID字符串(16进制表示)
     */
    std::string ExtractDeviceId(const std::vector<uint8_t>& message_data) const;
    
    /**
     * @brief 从消息中提取序列号
     * @param message_data 消息数据
     * @return 序列号
     */
    uint16_t ExtractSequenceNumber(const std::vector<uint8_t>& message_data) const;
    
    /**
     * @brief 从消息中提取消息ID
     * @param message_data 消息数据
     * @return 消息ID
     */
    uint16_t ExtractMessageId(const std::vector<uint8_t>& message_data) const;
    
    /**
     * @brief 生成会话键
     * @param device_id 设备ID
     * @param sequence_number 序列号
     * @return 会话键
     */
    std::string GenerateSessionKey(const std::string& device_id, uint16_t sequence_number) const;
    
    /**
     * @brief 重组完整消息
     * @param session 重组会话
     * @return 重组后的完整消息
     */
    std::vector<uint8_t> ReassembleMessage(const std::shared_ptr<ReassemblySession>& session) const;
    
    /**
     * @brief 计算重组后消息的CRC16
     * @param message_data 消息数据(不含CRC)
     * @return CRC16值
     */
    uint16_t CalculateCRC16(const std::vector<uint8_t>& message_data) const;
    
    /**
     * @brief 更新消息长度字段
     * @param message_data 消息数据
     * @param new_body_length 新的消息体长度
     */
    void UpdateMessageLength(std::vector<uint8_t>& message_data, uint16_t new_body_length) const;
    
private:
    mutable std::mutex sessions_mutex_;                                    // 会话互斥锁
    std::map<std::string, std::shared_ptr<ReassemblySession>> sessions_;  // 活跃的重组会话
    int timeout_seconds_;                                                  // 超时时间(秒)
    
    // 统计计数器
    mutable std::mutex stats_mutex_;
    uint64_t total_messages_processed_;     // 处理的消息总数
    uint64_t single_packet_messages_;       // 单包消息数
    uint64_t multi_packet_messages_;        // 多包消息数  
    uint64_t successful_reassemblies_;      // 成功重组数
    uint64_t timeout_sessions_;             // 超时会话数
    uint64_t error_packets_;                // 错误包数
    
    // 协议常量
    static constexpr uint16_t MSG_ID_BANKNOTE_REPORT = 12;  // 点钞上报消息ID
    static constexpr size_t HEADER_SIZE = 34;               // 协议头长度
    static constexpr size_t CRC_SIZE = 2;                   // CRC长度
    static constexpr size_t TAIL_SIZE = 2;                  // 协议尾长度
    static constexpr size_t MSG_ID_OFFSET = 6;              // 消息ID偏移
    static constexpr size_t DEVICE_ID_OFFSET = 8;           // 设备ID偏移
    static constexpr size_t DEVICE_ID_SIZE = 24;            // 设备ID长度
    static constexpr size_t SEQ_NUM_OFFSET = 32;            // 序列号偏移
    static constexpr size_t BODY_LENGTH_OFFSET = 3;         // 消息体长度偏移
    static constexpr size_t PACKET_TYPE_OFFSET = HEADER_SIZE + 1; // 分包标识偏移(信息类型后)
};
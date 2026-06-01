#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <atomic>
#include <mutex>
#include <thread>
#include <queue>
#include <condition_variable>
#include <functional>
#include <chrono>
#include <variant>

#include "Config.h"

#include "ResponseGenerator.h"
#include "logic/MultiProtocolManager.h"
#include "dpower/redis/Interfaces.h"
#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"

// 新增的头文件
#include "logic/handlers/MessageHandlerFactory.h"
#include "logic/services/DeviceService.h"
#include "logic/services/BanknoteService.h"
#include "logic/services/FaultService.h"
#include "logic/services/UpgradeService.h"
#include "logic/UniversalParser.h"

/**
 * @brief 映射后的消息数据，用于业务逻辑层
 */
struct MappedMessage {
    uint16_t msg_id;
    std::string source_ip;
    std::map<std::string, FieldValue> fields;
    bool is_valid;
    std::string error_message;
    
    // 辅助方法：获取字段值
    template<typename T>
    T GetField(const std::string& field_name, const T& default_value = T{}) const {
        auto it = fields.find(field_name);
        if (it != fields.end() && std::holds_alternative<T>(it->second)) {
            return std::get<T>(it->second);
        }
        return default_value;
    }
    
    // 检查字段是否存在
    bool HasField(const std::string& field_name) const {
        return fields.find(field_name) != fields.end();
    }
};

/**
 * @brief 消息处理统计信息快照（可拷贝）
 */
struct ProcessingStats {
    long long messages_processed = 0;
    long long messages_failed = 0;
    long long responses_generated = 0;
    long long total_processing_time_ms = 0;
    long long avg_processing_time_ms = 0;
    std::chrono::system_clock::time_point start_time;
    std::chrono::system_clock::time_point last_update_time;
    std::map<uint16_t, long long> message_type_counts;

    /**
     * @brief 获取统计信息的映射
     * @return 统计信息映射
     */
    std::map<std::string, long long> GetStatsMap() const;
};

/**
 * @brief 消息处理统计信息（内部使用）
 */
struct InternalProcessingStats {
    std::atomic<long long> messages_processed{0};
    std::atomic<long long> messages_failed{0};
    std::atomic<long long> responses_generated{0};
    std::atomic<long long> total_processing_time_ms{0};
    std::atomic<long long> avg_processing_time_ms{0};
    std::chrono::system_clock::time_point start_time;
    std::chrono::system_clock::time_point last_update_time;
    
    // 按消息类型统计
    std::map<uint16_t, long long> message_type_counts;
    mutable std::mutex stats_mutex;
    
    void UpdateStats(uint16_t msg_id, long long processing_time_ms);
    std::map<std::string, long long> GetStatsMap() const;
    void Reset();
};

/**
 * @brief 消息处理器
 */
class MessageProcessor : public std::enable_shared_from_this<MessageProcessor> {
public:
    /**
     * @brief 构造函数 (接收数据库和缓存客户端作为依赖)
     * @param db_client 指向数据库客户端的共享指针
     * @param cache_client 指向缓存客户端的共享指针
     */
    explicit MessageProcessor(
        std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
        std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
        std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
        const ParserConfig::FtpConfig& ftp_config
    );

    /**
     * @brief 析构函数
     */
    ~MessageProcessor();

    /**
     * @brief 初始化消息处理器
     * @param config 配置
     * @return 是否成功
     */
    bool Initialize(const ParserConfig& config);

    /**
     * @brief 启动消息处理
     * @return 是否成功
     */
    bool Start();

    /**
     * @brief 停止消息处理
     */
    void Stop();

    /**
     * @brief 检查是否在运行
     * @return 是否在运行
     */
    bool IsRunning() const;

    /**
     * @brief 处理单个消息
     * @param message Redis消息
     * @return 是否成功
     */
    bool ProcessMessage(const DPower::Redis::DPowerRedisMessage& message);

    /**
     * @brief 获取处理统计信息
     * @return 统计信息
     */
    ProcessingStats GetStats() const;

    /**
     * @brief 重置统计信息
     */
    void ResetStats();

    /**
     * @brief 设置消息处理回调
     * @param callback 回调函数
     */
    void SetMessageCallback(std::function<void(const UniversalParsedMessage&, const std::vector<uint8_t>&)> callback);

    /**
     * @brief 设置错误处理回调
     * @param callback 回调函数
     */
    void SetErrorCallback(std::function<void(const std::string&)> callback);

    /**
     * @brief 获取健康状态
     * @return 健康状态信息
     */
    std::map<std::string, std::string> GetHealthStatus() const;

    /**
     * @brief 执行健康检查
     * @return 是否健康
     */
    bool HealthCheck();

    /**
     * @brief 获取配置信息
     * @return 配置信息
     */
    ParserConfig GetConfig() const;

    /**
     * @brief 更新配置
     * @param config 新配置
     * @return 是否成功
     */
    bool UpdateConfig(const ParserConfig& config);



private:
    ParserConfig config_;
    std::shared_ptr<MultiProtocolManager> protocol_manager_;
    std::shared_ptr<ResponseGenerator> response_generator_;
    
    // 新增：服务层
    std::shared_ptr<DeviceService> device_service_;
    std::shared_ptr<BanknoteService> banknote_service_;
    std::shared_ptr<FaultService> fault_service_;
    std::shared_ptr<UpgradeService> upgrade_service_;
    
    // 设备离线检测由DeviceService管理
    
    // 新增：消息处理器工厂
    std::unique_ptr<MessageHandlerFactory> handler_factory_;
    
    // 新增：通用解析器
    std::shared_ptr<IUniversalParser> universal_parser_;
    
    // 多线程相关
    std::vector<std::thread> worker_threads_;
    std::atomic<bool> running_{false};
    std::atomic<bool> should_stop_{false};
    
    // 消息队列
    std::queue<DPower::Redis::DPowerRedisMessage> message_queue_;
    std::mutex queue_mutex_;
    std::condition_variable queue_cv_;
    
    // 统计信息
    InternalProcessingStats stats_;
    std::mutex stats_mutex_;
    
    // 回调函数
    std::function<void(const UniversalParsedMessage&, const std::vector<uint8_t>&)> message_callback_;
    std::function<void(const std::string&)> error_callback_;
    
    // 健康检查
    std::chrono::system_clock::time_point last_health_check_;
    std::chrono::system_clock::time_point last_message_time_;
    
    // 日志
    mutable std::mutex log_mutex_;

    // 数据库客户端
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    
    // 使用新的缓存客户端接口替换旧的内存缓存
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    
    // 消息队列客户端
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    
    // ftp服务器配置
    ParserConfig::FtpConfig ftp_config_; 

    /**
     * @brief 工作线程主函数
     * @param thread_id 线程ID
     */
    void WorkerThread(int thread_id);

    /**
     * @brief 消息读取线程
     */
    void ReaderThread();

    /**
     * @brief 统计更新线程
     */
    void StatsThread();

    /**
     * @brief 处理具体的消息类型（新架构）
     * @param parsed_msg 解析后的消息
     * @return 响应数据
     */
    std::vector<uint8_t> ProcessParsedMessage(const UniversalParsedMessage& parsed_msg);


    /**
     * @brief 发送响应到Redis
     * @param response_data 响应数据
     * @param source_ip 来源IP
     * @return 是否成功
     */
    bool SendResponse(const std::vector<uint8_t>& response_data, const std::string& source_ip);

    /**
     * @brief 记录日志
     * @param level 日志级别
     * @param message 日志消息
     */
    void Log(const std::string& level, const std::string& message) const;

    /**
     * @brief 记录性能日志
     * @param msg_id 消息ID
     * @param processing_time_ms 处理时间
     */
    void LogPerformance(uint16_t msg_id, long long processing_time_ms);

    /**
     * @brief 处理错误
     * @param error_msg 错误消息
     */
    void HandleError(const std::string& error_msg);

    /**
     * @brief 检查消息是否需要响应
     * @param msg_id 消息ID
     * @return 是否需要响应
     */
    bool ShouldRespond(uint16_t msg_id) const;

    /**
     * @brief 获取消息类型名称
     * @param msg_id 消息ID
     * @return 消息类型名称
     */
    std::string GetMessageTypeName(uint16_t msg_id) const;

    /**
     * @brief 验证消息有效性
     * @param parsed_msg 解析后的消息
     * @return 是否有效
     */
    bool ValidateMessage(const UniversalParsedMessage& parsed_msg) const;

    /**
     * @brief 更新最后消息时间
     */
    void UpdateLastMessageTime();

    /**
     * @brief 检查队列健康状态
     * @return 是否健康
     */
    bool CheckQueueHealth() const;

    /**
     * @brief 检查Redis连接健康状态
     * @return 是否健康
     */
    bool CheckRedisHealth() const;

    /**
     * @brief 格式化时间
     * @param tp 时间点
     * @return 格式化的时间字符串
     */
    std::string FormatTime(const std::chrono::system_clock::time_point& tp) const;

    /**
     * @brief 计算处理时间
     * @param start_time 开始时间
     * @return 处理时间(毫秒)
     */
    long long CalculateProcessingTime(const std::chrono::system_clock::time_point& start_time) const;
    
    /**
     * @brief 设置设备在线状态
     * @param device_id 设备ID
     * @param status 状态
     * @param source_ip 来源IP
     */
    // 设备状态管理由DeviceService处理
    
    /**
     * @brief 启动离线检测
     */
    void StartOfflineDetection();
    
    /**
     * @brief 初始化在线设备(从数据库加载)
     */
    void InitializeOnlineDevices();
    
    /**
     * @brief 停止离线检测
     */
    void StopOfflineDetection();
}; 

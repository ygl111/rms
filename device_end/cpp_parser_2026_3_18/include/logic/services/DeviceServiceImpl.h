#pragma once

#include "logic/services/DeviceService.h"
#include "logic/ResponseGenerator.h"
#include "logic/Config.h"
#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include <memory>
#include <mutex>
#include <unordered_map>
#include <chrono>
#include <thread>
#include <atomic>

/**
 * @brief 设备服务实现类
 */
class DeviceServiceImpl : public DeviceService {
public:
    DeviceServiceImpl(
        std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
        std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
        std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
        std::shared_ptr<ResponseGenerator> response_generator,
        const ParserConfig::FtpConfig& ftp_config,
        const ParserConfig::AuthConfig& auth_config
    );

    ~DeviceServiceImpl();

    // 实现DeviceService接口
    RegistrationResult RegisterDevice(const UniversalParsedMessage& parsed_msg) override;
    LoginResult LoginDevice(const UniversalParsedMessage& parsed_msg) override;
    std::vector<uint8_t> ProcessHeartbeat(const UniversalParsedMessage& parsed_msg) override;
    void UpdateDeviceStatus(const std::string& device_id, const std::string& status, const std::string& source_ip) override;
    std::optional<DPower::DB::DPowerUpgradeTask> GetUpgradeTask(const std::string& device_id) override;

    // 设备离线检测相关
    void StartOfflineDetection();
    void StopOfflineDetection();
    void InitializeOnlineDevices();

private:
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    std::shared_ptr<ResponseGenerator> response_generator_;
    ParserConfig::FtpConfig ftp_config_;
    ParserConfig::AuthConfig auth_config_;

    // 设备状态管理
    std::unordered_map<std::string, std::chrono::system_clock::time_point> device_last_heartbeat_;
    std::mutex device_status_mutex_;
    std::thread offline_detection_thread_;
    std::atomic<bool> offline_detection_running_{false};
    std::chrono::seconds heartbeat_timeout_{40};
    int sync_check_counter_{0};  // 双向同步检查计数器，每12次循环(60秒)执行一次

    // 日志函数
    void Log(const std::string& level, const std::string& message) const;
    
    // 离线检测线程函数
    void OfflineDetectionThread();
    
    // 辅助函数
    bool IsAllPaddingChars(const std::string& str);
}; 
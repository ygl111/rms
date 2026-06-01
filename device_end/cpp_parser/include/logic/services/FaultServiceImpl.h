#pragma once
#include "logic/services/FaultService.h"
#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include "dpower/notify/EmailNotifier.h"
#include <memory>

class FaultServiceImpl : public FaultService {
public:
    FaultServiceImpl(std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
                     std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
                     std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
                     DPower::Notify::EmailNotifierPtr email_notifier = nullptr);
    
    ~FaultServiceImpl() = default;
    
    FaultReportResult ProcessFaultReport(const UniversalParsedMessage& parsed_msg) override;
    
private:
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    DPower::Notify::EmailNotifierPtr email_notifier_;
    
    void Log(const std::string& level, const std::string& message) const;
    std::chrono::system_clock::time_point ParseBcdTime(const std::vector<uint8_t>& bcd_time);
    std::chrono::system_clock::time_point ParseBcdTimeString(const std::string& bcd_time_str);
}; 
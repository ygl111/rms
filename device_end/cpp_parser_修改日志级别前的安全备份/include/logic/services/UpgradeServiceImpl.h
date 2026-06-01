#pragma once
#include "logic/services/UpgradeService.h"
#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include <memory>

class UpgradeServiceImpl : public UpgradeService {
public:
    UpgradeServiceImpl(std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
                       std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
                       std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client);
    
    ~UpgradeServiceImpl() = default;
    
    UpgradeResultReportResult ProcessUpgradeResultReport(const UniversalParsedMessage& parsed_msg) override;
    
private:
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    
    void Log(const std::string& level, const std::string& message) const;
}; 
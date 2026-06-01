#pragma once
#include "logic/services/BanknoteService.h"
#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include <memory>

class BanknoteServiceImpl : public BanknoteService {
public:
    BanknoteServiceImpl(std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
                        std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
                        std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client);
    
    ~BanknoteServiceImpl() = default;
    
    BanknoteReportResult ProcessBanknoteReport(const UniversalParsedMessage& parsed_msg) override;
    
private:
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    
    void Log(const std::string& level, const std::string& message) const;
}; 
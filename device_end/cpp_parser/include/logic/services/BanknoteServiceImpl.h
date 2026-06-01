#pragma once
#include "logic/services/BanknoteService.h"
#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include "dpower/mq/Interfaces.h"
#include <memory>

class BanknoteServiceImpl : public BanknoteService {
public:
    BanknoteServiceImpl(std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
                        std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
                        std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
                        std::shared_ptr<DPower::MQ::DPowerMqClient> rabbitmq_client,
                        std::string worktime_queue_name);
    
    ~BanknoteServiceImpl() = default;
    
    BanknoteReportResult ProcessBanknoteReport(const UniversalParsedMessage& parsed_msg) override;
    
private:
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    std::shared_ptr<DPower::MQ::DPowerMqClient> rabbitmq_client_;
    std::string worktime_queue_name_;
    
    void Log(const std::string& level, const std::string& message) const;
}; 
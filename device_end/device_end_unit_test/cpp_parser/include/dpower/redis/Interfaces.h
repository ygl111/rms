#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <chrono>
#include <functional>

namespace DPower {
namespace Redis {

struct DPowerRedisResult {
    bool success;
    std::string value;
    std::string error_message;
};

struct DPowerRedisMessage {
    std::string id;
    std::string stream_key;
    std::string source_ip;
    std::string raw_data_base64;
    std::chrono::system_clock::time_point timestamp;
    std::map<std::string, std::string> additional_fields;
    bool IsValid() const { return !id.empty() && !raw_data_base64.empty(); }
};

struct DPowerRedisResponse {
    std::string client_id;
    std::string response_data_base64;
    std::chrono::system_clock::time_point timestamp;
};

class DPowerRedisClient {
public:
    virtual ~DPowerRedisClient() = default;
    virtual DPowerRedisResult Connect(const std::string& host, int port, const std::string& password, int db) = 0;
    virtual void Disconnect() = 0;
    virtual bool IsConnected() const = 0;
    virtual DPowerRedisResult Ping() const = 0;
    virtual DPowerRedisResult CreateConsumerGroup(const std::string& stream_key, const std::string& group_name, const std::string& start_id = "$") = 0;
    virtual std::vector<DPowerRedisMessage> ReadFromStream(const std::string& stream_key, const std::string& group_name, const std::string& consumer_name, int count, int block_timeout_ms) = 0;
    virtual DPowerRedisResult AckMessage(const std::string& stream_key, const std::string& group_name, const std::string& message_id) = 0;
    virtual DPowerRedisResult PushResponse(const std::string& queue_key, const DPowerRedisResponse& response) = 0;
    virtual int BatchPushResponse(const std::string& queue_key, const std::vector<DPowerRedisResponse>& responses) = 0;
    virtual long long GetStreamLength(const std::string& stream_key) const = 0;
    virtual long long GetQueueLength(const std::string& queue_key) const = 0;
    virtual long long GetPendingCount(const std::string& stream_key, const std::string& group_name) const = 0;
    virtual std::map<std::string, std::string> GetRedisInfo() const = 0;
    virtual std::map<std::string, std::string> GetConsumerGroupInfo(const std::string& stream_key) const = 0;
    virtual DPowerRedisResult SetKey(const std::string& key, const std::string& value, int ttl = 0) = 0;
    virtual std::string GetKey(const std::string& key) const = 0;
    virtual DPowerRedisResult DeleteKey(const std::string& key) = 0;
    virtual bool KeyExists(const std::string& key) const = 0;
    virtual long long TrimStream(const std::string& stream_key, long long max_length) const = 0;
    virtual std::map<std::string, long long> GetStatistics() const = 0;
    virtual void SetErrorHandler(std::function<void(const std::string&)> callback) = 0;
    virtual std::string GetLastError() const = 0;
    
    /**
     * @brief 执行任意 Redis 命令
     * @param command Redis 命令字符串
     * @return 命令执行结果
     */
    virtual DPowerRedisResult ExecuteCommand(const std::string& command) = 0;
};

class DPowerRedisClientFactory {
public:
    virtual ~DPowerRedisClientFactory() = default;
    virtual std::unique_ptr<DPowerRedisClient> Create() = 0;
};

std::unique_ptr<DPowerRedisClientFactory> CreateSwRedisFactory();

} // namespace Redis
} // namespace DPower

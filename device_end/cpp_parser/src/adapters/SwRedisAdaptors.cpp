#include "dpower/redis/Interfaces.h"
#include <sw/redis++/redis++.h>
#include <json.hpp>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <atomic>
#include <mutex>
#include <iterator>

using json = nlohmann::json;

namespace DPower {
namespace Redis {

namespace {

bool ParseStreamMessageReply(redisReply* message_reply,
                             const std::string& stream_key,
                             DPowerRedisMessage& msg) {
    if (!message_reply || message_reply->type != REDIS_REPLY_ARRAY || message_reply->elements != 2) {
        return false;
    }

    redisReply* id_reply = message_reply->element[0];
    redisReply* fields_reply = message_reply->element[1];
    if (!id_reply || id_reply->type != REDIS_REPLY_STRING || !fields_reply || fields_reply->type != REDIS_REPLY_ARRAY) {
        return false;
    }

    msg.id = std::string(id_reply->str, id_reply->len);
    for (size_t j = 0; j + 1 < fields_reply->elements; j += 2) {
        redisReply* key_reply = fields_reply->element[j];
        redisReply* val_reply = fields_reply->element[j + 1];
        if (!key_reply || key_reply->type != REDIS_REPLY_STRING || !val_reply || val_reply->type != REDIS_REPLY_STRING) {
            continue;
        }

        std::string key(key_reply->str, key_reply->len);
        std::string val(val_reply->str, val_reply->len);
        if (key == "raw_data_base64") {
            msg.raw_data_base64 = val;
        } else if (key == "source_ip") {
            msg.source_ip = val;
        } else if (key == "timestamp_ms") {
            try {
                long long ts_ms = std::stoll(val);
                msg.timestamp = std::chrono::system_clock::time_point(std::chrono::milliseconds(ts_ms));
            } catch (...) {
                // ignore parse error, timestamp keeps default value
            }
            msg.additional_fields[key] = val;
        } else {
            msg.additional_fields[key] = val;
        }
    }

    msg.stream_key = stream_key;
    return msg.IsValid();
}

} // namespace

//---------------------------------------------
// SwRedisClient 实现
//---------------------------------------------
class SwRedisClient : public DPowerRedisClient {
public:
    SwRedisClient() : redis_(nullptr), last_error_("") {}

    ~SwRedisClient() override {
        Disconnect();
    }

    // 连接管理
    DPowerRedisResult Connect(const std::string& host, int port, 
                             const std::string& password, int db) override {
        std::lock_guard<std::mutex> lock(redis_mutex_);
        try {
            sw::redis::ConnectionOptions connection_options;
            connection_options.host = host;
            connection_options.port = port;
            connection_options.password = password;
            connection_options.db = db;
            connection_options.socket_timeout = std::chrono::milliseconds(5000);
            connection_options.connect_timeout = std::chrono::milliseconds(5000);

            sw::redis::ConnectionPoolOptions pool_options;
            pool_options.size = 100;
            pool_options.wait_timeout = std::chrono::milliseconds(200);

            redis_ = std::make_unique<sw::redis::Redis>(connection_options, pool_options);
            
            // 测试连接
            redis_->ping();
            
            connection_string_ = host + ":" + std::to_string(port);
            std::cout << "Successfully connected to Redis: " << connection_string_ << std::endl;
            
            return {true, "", ""};
        } catch (const sw::redis::ReplyError& e) {
            return {false, "", "Redis reply error: " + std::string(e.what())};
        } catch (const sw::redis::TimeoutError& e) {
            return {false, "", "Redis timeout error: " + std::string(e.what())};
        } catch (const std::exception& e) {
            return {false, "", "Redis connection error: " + std::string(e.what())};
        }
    }

    void Disconnect() override {
        std::lock_guard<std::mutex> lock(redis_mutex_);
        if (redis_) {
            redis_.reset();
            std::cout << "Disconnected from Redis: " << connection_string_ << std::endl;
        }
    }

    bool IsConnected() const override {
        std::lock_guard<std::mutex> lock(redis_mutex_);
        return redis_ != nullptr;
    }

    DPowerRedisResult Ping() const override {
        if (!redis_) return {false, "", "Not connected"};
        try {
            redis_->ping();
            return {true, "PONG", ""};
        } catch (const std::exception& e) {
            return {false, "", "Ping failed: " + std::string(e.what())};
        }
    }

    // Stream操作
    DPowerRedisResult CreateConsumerGroup(const std::string& stream_key, 
                                         const std::string& group_name, 
                                         const std::string& start_id) override {
        if (!redis_) {
            return {false, "", "Not connected"};
        }

        try {
            redis_->xgroup_create(stream_key, group_name, start_id, true);
            return {true, "", ""};
        } catch (const sw::redis::ReplyError& e) {
            // 如果组已存在，不算错误
            if (std::string(e.what()).find("BUSYGROUP") != std::string::npos) {
                return {true, "", ""};
            }
            return {false, "", "Create consumer group failed: " + std::string(e.what())};
        } catch (const std::exception& e) {
            return {false, "", "Create consumer group error: " + std::string(e.what())};
        }
    }

    // [最终修正] 使用C风格API重写ReadFromStream以绕过库的bug
    std::vector<DPowerRedisMessage> ReadFromStream(const std::string& stream_key,
                                                   const std::string& group_name,
                                                   const std::string& consumer_name,
                                                   int count, 
                                                   int block_timeout_ms) override {
        std::vector<DPowerRedisMessage> messages;
        if (!redis_) return messages;

        try {
            auto reply = redis_->command("XREADGROUP", "GROUP", group_name, consumer_name, "COUNT", std::to_string(count), "BLOCK", std::to_string(block_timeout_ms), "STREAMS", stream_key, ">");

            if (reply && reply->type == REDIS_REPLY_ARRAY && reply->elements > 0) {
                redisReply* stream_reply_array = reply->element[0];
                if (stream_reply_array && stream_reply_array->type == REDIS_REPLY_ARRAY && stream_reply_array->elements == 2) {
                    redisReply* message_array = stream_reply_array->element[1];
                    if (message_array && message_array->type == REDIS_REPLY_ARRAY) {
                        for (size_t i = 0; i < message_array->elements; ++i) {
                            redisReply* message_reply = message_array->element[i];
                            DPowerRedisMessage msg;
                            if (ParseStreamMessageReply(message_reply, stream_key, msg)) {
                                messages.push_back(std::move(msg));
                                messages_read_++;
                            }
                        }
                    }
                }
            }
            return messages;
        } catch (const sw::redis::TimeoutError&) {
            return {};
        } catch (const std::exception& e) {
            HandleError("ReadFromStream error: " + std::string(e.what()));
            return {};
        }
    }

    std::vector<DPowerRedisMessage> AutoClaimPendingFromStream(const std::string& stream_key,
                                                               const std::string& group_name,
                                                               const std::string& consumer_name,
                                                               int min_idle_time_ms,
                                                               int count,
                                                               std::string& start_id) override {
        std::vector<DPowerRedisMessage> messages;
        if (!redis_) return messages;

        if (start_id.empty()) {
            start_id = "0-0";
        }

        if (!xautoclaim_supported_) {
            return ClaimPendingWithXClaim(stream_key, group_name, consumer_name, min_idle_time_ms, count);
        }

        try {
            auto reply = redis_->command("XAUTOCLAIM",
                                         stream_key,
                                         group_name,
                                         consumer_name,
                                         std::to_string(min_idle_time_ms),
                                         start_id,
                                         "COUNT",
                                         std::to_string(count));

            if (!reply || reply->type != REDIS_REPLY_ARRAY || reply->elements < 2) {
                return messages;
            }

            redisReply* next_start_reply = reply->element[0];
            if (next_start_reply && next_start_reply->type == REDIS_REPLY_STRING) {
                start_id = std::string(next_start_reply->str, next_start_reply->len);
            }

            redisReply* message_array = reply->element[1];
            if (!message_array || message_array->type != REDIS_REPLY_ARRAY) {
                return messages;
            }

            for (size_t i = 0; i < message_array->elements; ++i) {
                DPowerRedisMessage msg;
                if (ParseStreamMessageReply(message_array->element[i], stream_key, msg)) {
                    messages.push_back(std::move(msg));
                    messages_read_++;
                }
            }

            return messages;
        } catch (const sw::redis::TimeoutError&) {
            return {};
        } catch (const sw::redis::ReplyError& e) {
            const std::string err = e.what();
            if (err.find("unknown command") != std::string::npos && err.find("XAUTOCLAIM") != std::string::npos) {
                xautoclaim_supported_ = false;
                if (!xautoclaim_warned_) {
                    xautoclaim_warned_ = true;
                    std::cerr << "[WARN] Redis does not support XAUTOCLAIM, fallback to XPENDING+XCLAIM" << std::endl;
                }
                return ClaimPendingWithXClaim(stream_key, group_name, consumer_name, min_idle_time_ms, count);
            }
            HandleError("AutoClaimPendingFromStream error: " + err);
            return {};
        } catch (const std::exception& e) {
            HandleError("AutoClaimPendingFromStream error: " + std::string(e.what()));
            return {};
        }
    }

    DPowerRedisResult AckMessage(const std::string& stream_key,
                                const std::string& group_name,
                                const std::string& message_id) override {
        if (!redis_) {
            return {false, "", "Not connected"};
        }

        try {
            long long acked = redis_->xack(stream_key, group_name, message_id);
            if (acked > 0) {
                return {true, std::to_string(acked), ""};
            } else {
                return {false, "", "Message not found or already acknowledged"};
            }
        } catch (const std::exception& e) {
            return {false, "", "Ack message failed: " + std::string(e.what())};
        }
    }

    // List操作
    DPowerRedisResult PushResponse(const std::string& queue_key,
                                  const DPowerRedisResponse& response) override {
        if (!redis_) {
            return {false, "", "Not connected"};
        }

        try {
            json response_json;
            response_json["client_id"] = response.client_id;
            response_json["response_data_base64"] = response.response_data_base64;
            response_json["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
                response.timestamp.time_since_epoch()).count();

            std::string json_data = response_json.dump();
            redis_->lpush(queue_key, json_data);
            
            return {true, "", ""};
        } catch (const std::exception& e) {
            return {false, "", "Push response failed: " + std::string(e.what())};
        }
    }

    int BatchPushResponse(const std::string& queue_key,
                         const std::vector<DPowerRedisResponse>& responses) override {
        if (!redis_ || responses.empty()) {
            return 0;
        }

        try {
            std::vector<std::string> json_responses;
            json_responses.reserve(responses.size());

            for (const auto& response : responses) {
                json response_json;
                response_json["client_id"] = response.client_id;
                response_json["response_data_base64"] = response.response_data_base64;
                response_json["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
                    response.timestamp.time_since_epoch()).count();

                json_responses.push_back(response_json.dump());
            }

            redis_->lpush(queue_key, json_responses.begin(), json_responses.end());
            return static_cast<int>(responses.size());
        } catch (const std::exception& e) {
            HandleError("Batch push response failed: " + std::string(e.what()));
            return 0;
        }
    }

    // 统计和监控
    long long GetStreamLength(const std::string& stream_key) const override {
        if (!redis_) return 0;

        try {
            return redis_->xlen(stream_key);
        } catch (const std::exception& e) {
            HandleError("Get stream length failed: " + std::string(e.what()));
            return 0;
        }
    }

    long long GetQueueLength(const std::string& queue_key) const override {
        if (!redis_) return 0;

        try {
            return redis_->llen(queue_key);
        } catch (const std::exception& e) {
            HandleError("Get queue length failed: " + std::string(e.what()));
            return 0;
        }
    }

    long long GetPendingCount([[maybe_unused]] const std::string& stream_key, 
                            [[maybe_unused]] const std::string& group_name) const override {
        if (!redis_) return 0;

        try {
            // 简化实现，实际可能需要更复杂的逻辑
            return 0;
        } catch (const std::exception& e) {
            HandleError("Get pending count failed: " + std::string(e.what()));
            return 0;
        }
    }

    std::map<std::string, std::string> GetRedisInfo() const override {
        std::map<std::string, std::string> info;
        
        if (!redis_) return info;

        try {
            auto redis_info = redis_->info();
            
            std::istringstream iss(redis_info);
            std::string line;
            while (std::getline(iss, line)) {
                if (line.empty() || line[0] == '#') continue;
                
                size_t pos = line.find(':');
                if (pos != std::string::npos) {
                    std::string key = line.substr(0, pos);
                    std::string value = line.substr(pos + 1);
                    info[key] = value;
                }
            }
        } catch (const std::exception& e) {
            HandleError("Get Redis info failed: " + std::string(e.what()));
        }
        
        return info;
    }

    std::map<std::string, std::string> GetConsumerGroupInfo([[maybe_unused]] const std::string& stream_key) const override {
        std::map<std::string, std::string> result;
        
        if (!redis_) return result;

        try {
            // 简化实现，实际可能需要更复杂的逻辑
            auto reply = redis_->info();
            result["info"] = reply;
        } catch (const std::exception& e) {
            HandleError("Get consumer group info failed: " + std::string(e.what()));
        }
        
        return result;
    }

    // 键值操作
    DPowerRedisResult SetKey(const std::string& key, const std::string& value, int ttl) override {
        if (!redis_) {
            return {false, "", "Not connected"};
        }

        try {
            if (ttl > 0) {
                redis_->setex(key, std::chrono::seconds(ttl), value);
            } else {
                redis_->set(key, value);
            }
            return {true, "", ""};
        } catch (const std::exception& e) {
            return {false, "", "Set key failed: " + std::string(e.what())};
        }
    }

    std::string GetKey(const std::string& key) const override {
        if (!redis_) return "";

        try {
            auto result = redis_->get(key);
            return result.value_or("");
        } catch (const std::exception& e) {
            HandleError("Get key failed: " + std::string(e.what()));
            return "";
        }
    }

    DPowerRedisResult DeleteKey(const std::string& key) override {
        if (!redis_) {
            return {false, "", "Not connected"};
        }

        try {
            long long deleted = redis_->del(key);
            return {deleted > 0, std::to_string(deleted), ""};
        } catch (const std::exception& e) {
            return {false, "", "Delete key failed: " + std::string(e.what())};
        }
    }

    bool KeyExists(const std::string& key) const override {
        if (!redis_) return false;

        try {
            return redis_->exists(key) > 0;
        } catch (const std::exception& e) {
            HandleError("Key exists check failed: " + std::string(e.what()));
            return false;
        }
    }

    // 维护操作
    long long TrimStream(const std::string& stream_key, long long max_length) const override {
        if (!redis_) return 0;

        try {
            return redis_->xtrim(stream_key, max_length);
        } catch (const std::exception& e) {
            HandleError("Trim stream failed: " + std::string(e.what()));
            return 0;
        }
    }

    std::map<std::string, long long> GetStatistics() const override {
        std::lock_guard<std::mutex> lock(redis_mutex_);
        std::map<std::string, long long> stats;
        stats["messages_read"] = messages_read_.load();
        stats["messages_acked"] = messages_acked_.load();
        stats["responses_sent"] = responses_sent_.load();
        stats["errors_count"] = errors_count_.load();
        return stats;
    }

    // 错误处理
    void SetErrorHandler(std::function<void(const std::string&)> callback) override {
        std::lock_guard<std::mutex> lock(redis_mutex_);
        error_handler_ = callback;
    }

    std::string GetLastError() const override {
        std::lock_guard<std::mutex> lock(redis_mutex_);
        return last_error_;
    }

    DPowerRedisResult ExecuteCommand(const std::string& command) override {
        if (!redis_) {
            return {false, "", "Not connected"};
        }

        try {
            // 对于 FLUSHDB 命令，使用专门的方法
            if (command == "FLUSHDB") {
                redis_->flushdb();
                return {true, "OK", ""};
            }
            
            // 对于 KEYS 命令，使用专门的方法
            if (command.find("KEYS ") == 0) {
                std::string pattern = command.substr(5); // 去掉 "KEYS "
                std::vector<std::string> keys;
                redis_->keys(pattern, std::back_inserter(keys));
                std::string result;
                for (const auto& key : keys) {
                    if (!result.empty()) result += "\n";
                    result += key;
                }
                return {true, result, ""};
            }
            
            // 对于 DEL 命令，使用专门的方法
            if (command.find("DEL ") == 0) {
                std::string keys_str = command.substr(4); // 去掉 "DEL "
                std::istringstream iss(keys_str);
                std::vector<std::string> keys;
                std::string key;
                while (iss >> key) {
                    keys.push_back(key);
                }
                if (!keys.empty()) {
                    long long deleted = redis_->del(keys.begin(), keys.end());
                    return {true, std::to_string(deleted), ""};
                }
                return {true, "0", ""};
            }

            // 对于 LPUSH 命令，解析格式: LPUSH <key> <payload>
            if (command.find("LPUSH ") == 0) {
                const size_t key_start = 6;
                size_t key_end = command.find(' ', key_start);
                if (key_end == std::string::npos || key_end <= key_start) {
                    return {false, "", "Invalid LPUSH command format"};
                }
                std::string key = command.substr(key_start, key_end - key_start);
                std::string payload = command.substr(key_end + 1);
                long long pushed = redis_->lpush(key, payload);
                return {true, std::to_string(pushed), ""};
            }
            
            // 对于其他命令，尝试使用 eval 方法
            // 注意：这里可能需要根据具体命令进行调整
            return {false, "", "Unsupported command: " + command};
            
        } catch (const std::exception& e) {
            std::string error_msg = "Execute command failed: " + std::string(e.what());
            HandleError(error_msg);
            return {false, "", error_msg};
        }
    }

private:
    std::unique_ptr<sw::redis::Redis> redis_;
    std::string connection_string_;
    mutable std::string last_error_;
    std::function<void(const std::string&)> error_handler_;
    
    // 统计信息
    mutable std::atomic<long long> messages_read_{0};
    mutable std::atomic<long long> messages_acked_{0};
    mutable std::atomic<long long> responses_sent_{0};
    mutable std::atomic<long long> errors_count_{0};
    mutable std::mutex redis_mutex_;
    bool xautoclaim_supported_ = true;
    bool xautoclaim_warned_ = false;

    std::vector<DPowerRedisMessage> ClaimPendingWithXClaim(const std::string& stream_key,
                                                           const std::string& group_name,
                                                           const std::string& consumer_name,
                                                           int min_idle_time_ms,
                                                           int count) {
        std::vector<DPowerRedisMessage> messages;

        auto pending_reply = redis_->command("XPENDING",
                                             stream_key,
                                             group_name,
                                             "-",
                                             "+",
                                             std::to_string(count));

        if (!pending_reply || pending_reply->type != REDIS_REPLY_ARRAY || pending_reply->elements == 0) {
            return messages;
        }

        for (size_t i = 0; i < pending_reply->elements; ++i) {
            redisReply* pending_item = pending_reply->element[i];
            if (!pending_item || pending_item->type != REDIS_REPLY_ARRAY || pending_item->elements < 1) {
                continue;
            }

            redisReply* id_reply = pending_item->element[0];
            if (!id_reply || id_reply->type != REDIS_REPLY_STRING) {
                continue;
            }

            std::string message_id(id_reply->str, id_reply->len);
            auto claim_reply = redis_->command("XCLAIM",
                                               stream_key,
                                               group_name,
                                               consumer_name,
                                               std::to_string(min_idle_time_ms),
                                               message_id);

            if (!claim_reply || claim_reply->type != REDIS_REPLY_ARRAY || claim_reply->elements == 0) {
                continue;
            }

            for (size_t j = 0; j < claim_reply->elements; ++j) {
                DPowerRedisMessage msg;
                if (ParseStreamMessageReply(claim_reply->element[j], stream_key, msg)) {
                    messages.push_back(std::move(msg));
                    messages_read_++;
                }
            }
        }

        return messages;
    }

    void HandleError(const std::string& error_msg) const {
        last_error_ = error_msg;
        errors_count_++;
        
        if (error_handler_) {
            error_handler_(error_msg);
        } else {
            std::cerr << "[ERROR] " << error_msg << std::endl;
        }
    }

    std::vector<DPowerRedisMessage> ParseStreamMessages(
        const std::vector<std::pair<std::string, std::vector<std::pair<std::string, std::vector<std::pair<std::string, std::string>>>>>>& stream_messages,
        const std::string& stream_key) {
        
        std::vector<DPowerRedisMessage> messages;
        
        for (const auto& stream_pair : stream_messages) {
            const std::string& current_stream_key = stream_pair.first;
            const auto& message_list = stream_pair.second;
            
            if (current_stream_key != stream_key) continue;
            
            for (const auto& message_pair : message_list) {
                const std::string& message_id = message_pair.first;
                const auto& field_list = message_pair.second;
                
                DPowerRedisMessage message;
                message.id = message_id;
                message.stream_key = stream_key;
                message.timestamp = std::chrono::system_clock::now();
                
                for (const auto& field_pair : field_list) {
                    const std::string& field_name = field_pair.first;
                    const std::string& field_value = field_pair.second;
                    
                    if (field_name == "raw_data_base64") {
                        message.raw_data_base64 = field_value;
                    } else if (field_name == "source_ip") {
                        message.source_ip = field_value;
                    } else if (field_name == "timestamp_ms") {
                        try {
                            long long timestamp_ms = std::stoll(field_value);
                            message.timestamp = std::chrono::system_clock::from_time_t(timestamp_ms / 1000);
                        } catch (...) {
                            // 使用当前时间作为fallback
                        }
                    } else {
                        message.additional_fields[field_name] = field_value;
                    }
                }
                
                if (message.IsValid()) {
                    messages.push_back(message);
                    messages_read_++;
                }
            }
        }
        
        return messages;
    }
};

//---------------------------------------------
// SwRedisClientFactory 实现
//---------------------------------------------
class SwRedisClientFactory : public DPowerRedisClientFactory {
public:
    std::unique_ptr<DPowerRedisClient> Create() override {
        return std::make_unique<SwRedisClient>();
    }
};

//---------------------------------------------
// 外部可见工厂函数
//---------------------------------------------
std::unique_ptr<DPowerRedisClientFactory> CreateSwRedisFactory() {
    return std::make_unique<SwRedisClientFactory>();
}

} // namespace Redis
} // namespace DPower
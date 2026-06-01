#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include <json.hpp>
#include <iostream>
#include <sstream>
#include "logic/utils/MessageUtils.h"

using json = nlohmann::json;

// 将JSON转换函数移动到 DPower::DB 命名空间以利用ADL
namespace DPower {
namespace DB {

// --- 数据结构与JSON的相互转换 ---
void to_json(json& j, const DPowerDeviceRecord& p) {
    // 约定：p.auth_code 按十六进制字符串（32个hex字符，表示16字节）存储
    // 为避免再次 hex 编码导致长度膨胀，这里直接以字符串形式写入缓存
    auto safe_utf8 = [](const std::string& s) -> std::string {
        if (MessageUtils::IsValidUtf8(s)) return s;
        // 回退为十六进制展示，避免 JSON 抛 invalid UTF-8 异常
        std::ostringstream oss; oss << "[HEX:";
        for (unsigned char c : s) oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
        oss << "]"; return oss.str();
    };
    j = json{
        {"device_id", safe_utf8(p.device_id)},
        {"model_name", safe_utf8(p.model_name)},
        {"auth_code_hex", p.auth_code}
        // 可根据需要添加更多需要缓存的字段
    };
}

void from_json(const json& j, DPowerDeviceRecord& p) {
    j.at("device_id").get_to(p.device_id);
    j.at("model_name").get_to(p.model_name);
    // 从缓存中恢复十六进制字符串形式的鉴权码（32个hex字符）
    if (j.contains("auth_code_hex") && j["auth_code_hex"].is_string()) {
        p.auth_code = j["auth_code_hex"].get<std::string>();
    } else {
        p.auth_code.clear();
    }
}

void to_json(json& j, const DPowerUpgradeTask& p) {
    j = json{
        {"task_id", p.task_id},
        {"task_code", p.task_code},
        {"model_id", p.model_id},
        {"status", p.status},
        {"start_date", std::chrono::duration_cast<std::chrono::seconds>(p.start_date.time_since_epoch()).count()},
        {"end_date", std::chrono::duration_cast<std::chrono::seconds>(p.end_date.time_since_epoch()).count()},
        {"device_task_status", p.device_task_status},
        {"confirm_upgrade", p.confirm_upgrade},
        {"force_upgrade", p.force_upgrade},
        {"time_arrange_start", p.time_arrange_start},
        {"time_arrange_end", p.time_arrange_end},
        {"module_type", p.module_type},
        {"firmware_id", p.firmware_id},
        {"firmware_name", p.firmware_name},
        {"firmware_version", p.firmware_version},
        {"file_size", p.file_size},
        {"md5_hash", p.md5_hash},
        {"storage_path", p.storage_path},
        {"ftp_host", p.ftp_host},
        {"ftp_port", p.ftp_port},
        {"ftp_dir", p.ftp_dir},
        {"download_url", p.download_url}
    };
}

void from_json(const json& j, DPowerUpgradeTask& p) {
    j.at("task_id").get_to(p.task_id);
    j.at("task_code").get_to(p.task_code);
    j.at("model_id").get_to(p.model_id);
    j.at("status").get_to(p.status);
    
    // 时间字段处理
    auto start_seconds = j.at("start_date").get<int64_t>();
    p.start_date = std::chrono::system_clock::from_time_t(start_seconds);
    
    auto end_seconds = j.at("end_date").get<int64_t>();
    p.end_date = std::chrono::system_clock::from_time_t(end_seconds);
    
    j.at("device_task_status").get_to(p.device_task_status);
    j.at("confirm_upgrade").get_to(p.confirm_upgrade);
    j.at("force_upgrade").get_to(p.force_upgrade);
    j.at("time_arrange_start").get_to(p.time_arrange_start);
    j.at("time_arrange_end").get_to(p.time_arrange_end);
    j.at("module_type").get_to(p.module_type);
    j.at("firmware_id").get_to(p.firmware_id);
    j.at("firmware_name").get_to(p.firmware_name);
    j.at("firmware_version").get_to(p.firmware_version);
    j.at("file_size").get_to(p.file_size);
    j.at("md5_hash").get_to(p.md5_hash);
    j.at("storage_path").get_to(p.storage_path);
    j.at("ftp_host").get_to(p.ftp_host);
    j.at("ftp_port").get_to(p.ftp_port);
    j.at("ftp_dir").get_to(p.ftp_dir);
    j.at("download_url").get_to(p.download_url);
}

} // namespace DB
} // namespace DPower


namespace DPower {
namespace Cache {

namespace { // 匿名命名空间，用于隐藏实现细节

// --- Redis 缓存客户端实现 ---
class RedisCacheClient : public DPowerCacheClient {
public:
    explicit RedisCacheClient(std::shared_ptr<Redis::DPowerRedisClient> redis_client)
        : redis_(std::move(redis_client)) {}

    // --- 设备记录缓存实现 ---
    std::optional<DB::DPowerDeviceRecord> GetDevice(const std::string& device_id) override {
        std::string key = "cache:device:" + device_id;
        std::cout << "[CACHE DEBUG] Getting device from cache with key: " << key << std::endl;
        std::string json_str = redis_->GetKey(key);
        if (json_str.empty()) {
            std::cout << "[CACHE DEBUG] Cache MISS for key: " << key << std::endl;
            return std::nullopt; // 缓存未命中
        }
        std::cout << "[CACHE DEBUG] Cache HIT for key: " << key << ", Value: " << json_str << std::endl;
        try {
            return json::parse(json_str).get<DB::DPowerDeviceRecord>();
        } catch (...) {
            return std::nullopt; // JSON 解析失败
        }
    }

    void SetDevice(const DB::DPowerDeviceRecord& record, int ttl_seconds) override {
        std::string key = "cache:device:" + record.device_id;
        std::string json_str;
        try {
            json_str = json(record).dump();
        } catch (const std::exception& e) {
            // 回退：对关键字符串做 UTF-8 校验并使用安全表示
            auto safe_utf8 = [](const std::string& s) -> std::string {
                if (MessageUtils::IsValidUtf8(s)) return s;
                std::ostringstream oss; oss << "[HEX:";
                for (unsigned char c : s) oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
                oss << "]"; return oss.str();
            };
            auto escape_json = [](const std::string& s) -> std::string {
                std::string out; out.reserve(s.size()+4);
                for (unsigned char c : s) {
                    switch (c) {
                        case '"': out += "\\\""; break;
                        case '\\': out += "\\\\"; break;
                        case '\b': out += "\\b"; break;
                        case '\f': out += "\\f"; break;
                        case '\n': out += "\\n"; break;
                        case '\r': out += "\\r"; break;
                        case '\t': out += "\\t"; break;
                        default:
                            if (c < 0x20) { char buf[7]; std::snprintf(buf, sizeof(buf), "\\u%04x", c); out += buf; }
                            else out += static_cast<char>(c);
                    }
                }
                return out;
            };
            std::string dev = escape_json(safe_utf8(record.device_id));
            std::string model = escape_json(safe_utf8(record.model_name));
            std::string code = escape_json(record.auth_code);
            json_str = std::string("{") +
                       "\"device_id\":\"" + dev + "\"," +
                       "\"model_name\":\"" + model + "\"," +
                       "\"auth_code_hex\":\"" + code + "\"}";
            std::cerr << "[CACHE WARN] JSON dump failed, used sanitized fallback: " << e.what() << std::endl;
        }
        std::cout << "[CACHE DEBUG] Setting device cache for key: " << key << " with TTL: " << ttl_seconds << "s" << std::endl;
        redis_->SetKey(key, json_str, ttl_seconds);
    }

    void InvalidateDevice(const std::string& device_id) override {
        std::string key = "cache:device:" + device_id;
        std::cout << "[CACHE DEBUG] Invalidating device cache for key: " << key << std::endl;
        redis_->DeleteKey(key);
    }

    // --- 升级任务缓存实现 ---
    std::optional<std::optional<DB::DPowerUpgradeTask>> GetUpgradeTask(const std::string& device_id) override {
        std::string key = "cache:task:" + device_id;
        std::cout << "[CACHE DEBUG] Getting task from cache with key: " << key << std::endl;
        std::string json_str = redis_->GetKey(key);
        if (json_str.empty()) {
            std::cout << "[CACHE DEBUG] Cache MISS for key: " << key << std::endl;
            return std::nullopt; // 缓存未命中
        }
        std::cout << "[CACHE DEBUG] Cache HIT for key: " << key << ", Value: " << json_str << std::endl;
        try {
            if (json_str == "null") {
                return std::make_optional(std::optional<DB::DPowerUpgradeTask>{});
            }
            return json::parse(json_str).get<DB::DPowerUpgradeTask>();
        } catch (...) {
            return std::nullopt; // JSON 解析失败
        }
    }

    void SetUpgradeTask(const std::string& device_id, const std::optional<DB::DPowerUpgradeTask>& task, int ttl_seconds) override {
        std::string key = "cache:task:" + device_id;
        std::string json_str = task ? json(*task).dump() : "null";
        std::cout << "[CACHE DEBUG] Setting task cache for key: " << key << " with TTL: " << ttl_seconds << "s, Value: " << json_str << std::endl;
        redis_->SetKey(key, json_str, ttl_seconds);
    }

    bool ClearAllCache() override {
        std::cout << "[CACHE DEBUG] Clearing all cache data..." << std::endl;
        try {
            // 使用 FLUSHDB 命令清除当前数据库中的所有键
            // 注意：这里假设缓存使用独立的数据库（db + 1）
            auto result = redis_->ExecuteCommand("FLUSHDB");
            if (result.success) {
                std::cout << "[CACHE DEBUG] All cache data cleared successfully" << std::endl;
                return true;
            } else {
                std::cerr << "[CACHE ERROR] Failed to clear cache: " << result.error_message << std::endl;
                return false;
            }
        } catch (const std::exception& e) {
            std::cerr << "[CACHE ERROR] Exception while clearing cache: " << e.what() << std::endl;
            return false;
        }
    }

    bool ClearAllUpgradeLocks() override {
        std::cout << "[CACHE DEBUG] Clearing all upgrade push locks..." << std::endl;
        try {
            // 使用 KEYS 命令查找所有升级推送锁
            auto keys_result = redis_->ExecuteCommand("KEYS lock:upgrade_push:*");
            if (!keys_result.success) {
                std::cerr << "[CACHE ERROR] Failed to get upgrade lock keys: " << keys_result.error_message << std::endl;
                return false;
            }

            // 解析返回的键列表
            std::vector<std::string> lock_keys;
            std::istringstream iss(keys_result.value);
            std::string key;
            while (std::getline(iss, key, '\n')) {
                if (!key.empty() && key.find("lock:upgrade_push:") == 0) {
                    lock_keys.push_back(key);
                }
            }

            if (lock_keys.empty()) {
                std::cout << "[CACHE DEBUG] No upgrade push locks found" << std::endl;
                return true;
            }

            // 批量删除所有锁
            std::string del_command = "DEL";
            for (const auto& lock_key : lock_keys) {
                del_command += " " + lock_key;
            }

            auto del_result = redis_->ExecuteCommand(del_command);
            if (del_result.success) {
                std::cout << "[CACHE DEBUG] Successfully cleared " << lock_keys.size() << " upgrade push locks" << std::endl;
                return true;
            } else {
                std::cerr << "[CACHE ERROR] Failed to delete upgrade locks: " << del_result.error_message << std::endl;
                return false;
            }
        } catch (const std::exception& e) {
            std::cerr << "[CACHE ERROR] Exception while clearing upgrade locks: " << e.what() << std::endl;
            return false;
        }
    }

    bool KeyExists(const std::string& key) const override {
        try {
            return redis_->KeyExists(key);
        } catch (const std::exception& e) {
            std::cerr << "[CACHE ERROR] Exception while checking key existence: " << e.what() << std::endl;
            return false;
        }
    }

    void SetKey(const std::string& key, const std::string& value, int ttl_seconds) override {
        try {
            auto result = redis_->SetKey(key, value, ttl_seconds);
            if (!result.success) {
                std::cerr << "[CACHE ERROR] Failed to set key: " << result.error_message << std::endl;
            }
        } catch (const std::exception& e) {
            std::cerr << "[CACHE ERROR] Exception while setting key: " << e.what() << std::endl;
        }
    }

private:
    std::shared_ptr<Redis::DPowerRedisClient> redis_;
};


// --- Redis 缓存工厂实现 ---
class RedisCacheFactory : public DPowerCacheFactory {
public:
    CacheClientPtr Create(std::shared_ptr<Redis::DPowerRedisClient> redis_client) override {
        if (!redis_client) {
            return nullptr;
        }
        return std::make_unique<RedisCacheClient>(std::move(redis_client));
    }
};

} // 匿名命名空间结束


// --- 对外可见的工厂创建函数 ---
CacheFactoryPtr CreateRedisCacheFactory() {
    return std::make_unique<RedisCacheFactory>();
}

} // namespace Cache
} // namespace DPower

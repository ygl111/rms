#include "dpower/redis/Interfaces.h"

// 若使用真实 redis++ (sw::redis)，取消以下宏定义
#define USE_SW_REDIS 1

#if USE_SW_REDIS
#include <sw/redis++/redis++.h>
#endif

#include <chrono>
#include <memory>
#include <utility>

namespace DPower {
namespace Redis {

//--------------------------------------------------
// SwRedisClient 实现
//--------------------------------------------------
class SwRedisClient : public DPowerRedisClient {
public:
    SwRedisClient() = default;

    DPowerRedisResult Connect(const std::string& host, int port, 
                             const std::string& password = "", int db = 0) override {
        DPowerRedisResult res;
        try {
#if USE_SW_REDIS
            sw::redis::ConnectionOptions opts;
            opts.host = host;
            opts.port = port;
            if (!password.empty()) {
                opts.password = password;
            }
            opts.db = db;
            opts.socket_timeout = std::chrono::milliseconds(5000);
            opts.connect_timeout = std::chrono::milliseconds(5000);
            redis_ = std::make_unique<sw::redis::Redis>(opts);
            // 简单 ping 验证
            redis_->ping();
#endif
            res.success = true;
        } catch (const std::exception& e) {
            res.success = false;
            res.error_message = e.what();
        }
        return res;
    }

    bool IsConnected() const override {
#if USE_SW_REDIS
        return redis_ != nullptr;
#else
        return true;
#endif
    }

    DPowerRedisResult StreamAdd(const std::string& stream,
                                const std::map<std::string, std::string>& fields) override {
        DPowerRedisResult res;
        try {
#if USE_SW_REDIS
            auto id = redis_->xadd(stream, "*", fields.begin(), fields.end());
            res.data = id;
#endif
            res.success = true;
        } catch (const std::exception& e) {
            res.success = false;
            res.error_message = e.what();
        }
        return res;
    }

    DPowerRedisResult ListBlockingPop(const std::string& key, int timeout_ms) override {
        DPowerRedisResult res;
        try {
#if USE_SW_REDIS
            // 将毫秒转换为秒
	    auto timeout_in_seconds = std::chrono::seconds(timeout_ms / 1000);
	    // 使用正确的 'seconds' 类型调用 blpop
	    auto pair = redis_->blpop(key, timeout_in_seconds);
            if (pair) {
                res.success = true;
                res.data = pair->second;
            } else {
                res.success = false;
                res.error_message = "timeout"; // 与旧实现保持一致
            }
#else
            // 占位模拟：始终超时
            (void)key; (void)timeout_ms;
            res.success = false;
            res.error_message = "timeout";
#endif
        } catch (const std::exception& e) {
            res.success = false;
            res.error_message = e.what();
        }
        return res;
    }

private:
#if USE_SW_REDIS
    std::unique_ptr<sw::redis::Redis> redis_;
#endif
};

//--------------------------------------------------
// 工厂
//--------------------------------------------------
class SwRedisFactory : public DPowerRedisClientFactory {
public:
    std::unique_ptr<DPowerRedisClient> Create() override {
        return std::make_unique<SwRedisClient>();
    }
};

//--------------------------------------------------
// 外部可见函数
//--------------------------------------------------
std::unique_ptr<DPowerRedisClientFactory> CreateSwRedisFactory() {
    return std::make_unique<SwRedisFactory>();
}

} // namespace Redis
} // namespace DPower 

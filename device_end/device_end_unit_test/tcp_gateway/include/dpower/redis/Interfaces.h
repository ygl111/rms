#pragma once
// ================================================================
//  DPower::Redis 抽象接口
//  业务层仅依赖这些接口，实现可由 redis++ / hiredis 等替换
// ================================================================

#include <map>
#include <memory>
#include <string>

namespace DPower {
namespace Redis {

//---------------------------------------------
// 结果结构体
//---------------------------------------------
struct DPowerRedisResult {
    bool        success { false };
    std::string data;           // 成功时数据
    std::string error_message;  // 失败时错误信息（或 "timeout"）
};

//---------------------------------------------
// 抽象客户端
//---------------------------------------------
class DPowerRedisClient {
public:
    virtual DPowerRedisResult Connect(const std::string& host, int port, 
                                     const std::string& password = "", int db = 0) = 0;
    virtual bool IsConnected() const = 0;

    virtual DPowerRedisResult StreamAdd(
        const std::string& stream,
        const std::map<std::string, std::string>& fields) = 0;

    // timeout_ms = 0 表示无限阻塞
    virtual DPowerRedisResult ListBlockingPop(const std::string& key, int timeout_ms) = 0;

    virtual ~DPowerRedisClient() = default;
};

//---------------------------------------------
// 工厂
//---------------------------------------------
class DPowerRedisClientFactory {
public:
    virtual std::unique_ptr<DPowerRedisClient> Create() = 0;
    virtual ~DPowerRedisClientFactory() = default;
};

//---------------------------------------------
// 提供工厂实例的函数（由适配器实现）
//---------------------------------------------
std::unique_ptr<DPowerRedisClientFactory> CreateSwRedisFactory();

} // namespace Redis
} // namespace DPower 
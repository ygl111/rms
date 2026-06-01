#pragma once
// ================================================================
//  DPower::Cache 抽象接口
//  业务层仅依赖此接口，用于缓存数据库查询结果。
// ================================================================

#include "dpower/db/Interfaces.h"
#include "dpower/redis/Interfaces.h" // 包含Redis接口定义以解析类型
#include <string>
#include <memory>
#include <optional>

namespace DPower {
namespace Cache {

//---------------------------------------------
// 前向声明 & 智能指针别名
//---------------------------------------------
class DPowerCacheClient;
class DPowerCacheFactory;

using CacheClientPtr = std::unique_ptr<DPowerCacheClient>;
using CacheFactoryPtr = std::unique_ptr<DPowerCacheFactory>;

//---------------------------------------------
// 抽象缓存客户端接口
//---------------------------------------------
class DPowerCacheClient {
public:
    virtual ~DPowerCacheClient() = default;

    // --- 设备记录缓存 ---
    
    /**
     * @brief 尝试从缓存中获取设备记录
     * @param device_id 设备的唯一ID
     * @return 如果命中缓存则返回设备记录，否则返回 std::nullopt
     */
    virtual std::optional<DB::DPowerDeviceRecord> GetDevice(const std::string& device_id) = 0;

    /**
     * @brief 将设备记录存入缓存
     * @param record 要缓存的设备记录
     * @param ttl_seconds 缓存过期时间（秒），0表示永不过期
     */
    virtual void SetDevice(const DB::DPowerDeviceRecord& record, int ttl_seconds) = 0;

    /**
     * @brief 从缓存中移除设备记录
     * @param device_id 设备的唯一ID
     */
    virtual void InvalidateDevice(const std::string& device_id) = 0;


    // --- 升级任务缓存 ---

    /**
     * @brief 尝试从缓存中获取设备的升级任务
     * @param device_id 设备的唯一ID
     * @return 如果命中缓存，返回一个 optional。如果 optional 中有值，表示有任务；
     * 如果 optional 中无值(nullopt)，表示确定没有任务。
     * 如果函数本身返回 nullopt，表示缓存中没有此信息。
     */
    virtual std::optional<std::optional<DB::DPowerUpgradeTask>> GetUpgradeTask(const std::string& device_id) = 0;

    /**
     * @brief 将设备的升级任务状态存入缓存
     * @param device_id 设备的唯一ID
     * @param task 如果有任务，则传入任务详情；如果没有，则传入 std::nullopt
     * @param ttl_seconds 缓存过期时间（秒）
     */
    virtual void SetUpgradeTask(const std::string& device_id, const std::optional<DB::DPowerUpgradeTask>& task, int ttl_seconds) = 0;

    /**
     * @brief 清除所有缓存数据
     * @return 清除是否成功
     */
    virtual bool ClearAllCache() = 0;

    /**
     * @brief 清除所有升级推送锁
     * @return 清除是否成功
     */
    virtual bool ClearAllUpgradeLocks() = 0;

    // --- 通用键值操作 ---

    /**
     * @brief 检查键是否存在
     * @param key 要检查的键
     * @return 键是否存在
     */
    virtual bool KeyExists(const std::string& key) const = 0;

    /**
     * @brief 设置键值对
     * @param key 键
     * @param value 值
     * @param ttl_seconds 过期时间（秒），0表示永不过期
     */
    virtual void SetKey(const std::string& key, const std::string& value, int ttl_seconds = 0) = 0;
};


//---------------------------------------------
// 缓存工厂接口
//---------------------------------------------
class DPowerCacheFactory {
public:
    virtual ~DPowerCacheFactory() = default;

    /**
     * @brief 创建一个缓存客户端实例
     * @param redis_client 一个指向已连接Redis客户端的共享指针
     * @return CacheClientPtr 指向缓存客户端实例的智能指针
     */
    virtual CacheClientPtr Create(std::shared_ptr<Redis::DPowerRedisClient> redis_client) = 0;
};


//---------------------------------------------
// 提供工厂实例的函数（由适配器实现）
//---------------------------------------------
CacheFactoryPtr CreateRedisCacheFactory();

} // namespace Cache
} // namespace DPower

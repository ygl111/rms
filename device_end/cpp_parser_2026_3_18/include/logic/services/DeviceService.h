#pragma once

#include <string>
#include <optional>
#include <vector>
#include "logic/UniversalParser.h"
#include "dpower/db/Interfaces.h"

/**
 * @brief 设备注册结果
 */
struct RegistrationResult {
    bool success;
    std::string error_message;
    std::vector<uint8_t> auth_code;
    uint8_t result_code; // 0x00-成功, 0x01-失败, 0x02-设备已注册, 0x03-协议错误
};

/**
 * @brief 设备登录结果
 */
struct LoginResult {
    bool success;
    std::string error_message;
    uint8_t result_code; // 0x00-成功, 0x01-失败, 0x02-无效鉴权码
    uint8_t keep_connect;
};

/**
 * @brief 设备服务接口
 * 抽象设备相关的业务逻辑
 */
class DeviceService {
public:
    virtual ~DeviceService() = default;
    
    /**
     * @brief 注册设备
     * @param parsed_msg 解析后的消息
     * @return 注册结果
     */
    virtual RegistrationResult RegisterDevice(const UniversalParsedMessage& parsed_msg) = 0;
    
    /**
     * @brief 设备登录
     * @param parsed_msg 解析后的消息
     * @return 登录结果
     */
    virtual LoginResult LoginDevice(const UniversalParsedMessage& parsed_msg) = 0;
    
    /**
     * @brief 处理心跳
     * @param parsed_msg 解析后的消息
     * @return 心跳响应数据
     */
    virtual std::vector<uint8_t> ProcessHeartbeat(const UniversalParsedMessage& parsed_msg) = 0;
    
    /**
     * @brief 更新设备状态
     * @param device_id 设备ID
     * @param status 状态
     * @param source_ip 源IP
     */
    virtual void UpdateDeviceStatus(const std::string& device_id, const std::string& status, const std::string& source_ip) = 0;
    
    /**
     * @brief 获取设备升级任务
     * @param device_id 设备ID
     * @return 升级任务（如果存在）
     */
    virtual std::optional<DPower::DB::DPowerUpgradeTask> GetUpgradeTask(const std::string& device_id) = 0;
    
    /**
     * @brief 启动离线检测
     */
    virtual void StartOfflineDetection() = 0;
    
    /**
     * @brief 初始化在线设备(从数据库加载)
     */
    virtual void InitializeOnlineDevices() = 0;
    
    /**
     * @brief 停止离线检测
     */
    virtual void StopOfflineDetection() = 0;
}; 
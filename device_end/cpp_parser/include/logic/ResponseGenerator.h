#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <cstdint>
#include <ctime>
#include <chrono>
#include "logic/Config.h" // 包含配置类的定义
#include "logic/UniversalParser.h"
#include "logic/MultiProtocolManager.h"
#include "dpower/utils/Auth.h"
#include "dpower/db/Interfaces.h" // 包含数据库接口定义

/**
 * @brief 响应生成器
 */
class ResponseGenerator {
public:
    struct BodyBuildContext {
        uint32_t seq_num = 0;
        uint16_t response_msg_id = 0;
        uint8_t result = 0;
        uint8_t keep_connect = 0;
        uint8_t heart_interval = 0;
        uint32_t set_maintenance_threshold = 0xFFFFFFFF; // 设置的维护阈值，0xFFFFFFFF表示未设置
        std::vector<uint8_t> server_time_bcd; // 长度6
        std::vector<uint8_t> authentication_code; // 长度依协议
        std::string additional_msg; // 可选
    // 额外字段：用于承载协议体内的动态字节（例如升级相关字段），键名与 JSON 中的字段 name 对应
    std::map<std::string, std::vector<uint8_t>> extras;
    };
    /**
     * @brief 构造函数
     */
    ResponseGenerator();

    /**
     * @brief 析构函数
     */
    ~ResponseGenerator();

    /**
     * @brief 初始化响应生成器
     * @param universal_parser 通用解析器实例
     * @param protocol_manager 多协议管理器实例
     * @return 是否初始化成功
     */
    bool Initialize(std::shared_ptr<IUniversalParser> universal_parser, 
                   std::shared_ptr<MultiProtocolManager> protocol_manager);

    /**
     * @brief 创建注册响应
     */
    std::vector<uint8_t> CreateRegistrationResponse(const UniversalParsedMessage& request_msg,
                                                  uint8_t result_code = 0x00,
                                                  const std::vector<uint8_t>& authentication_code = {});

    /**
     * @brief 创建登录响应
     */
    std::vector<uint8_t> CreateLoginResponse(const UniversalParsedMessage& request_msg, uint8_t status_code, uint8_t keep_connect = 0);

    /**
     * @brief 创建心跳响应
     * @param request_msg 请求消息
     * @param keep_connect 长连接保持标志：0=可断开，1=保持连接
     * @param set_maintenance_threshold 设置的维护阈值，0xFFFFFFFF表示未设置
     */
    std::vector<uint8_t> CreateHeartbeatResponse(const UniversalParsedMessage& request_msg, uint8_t keep_connect, uint32_t set_maintenance_threshold = 0xFFFFFFFF);

    /**
     * @brief 创建通用响应
     */
    std::vector<uint8_t> CreateGenericResponse(const UniversalParsedMessage& request_msg, uint8_t result = 0x00, 
                                               const std::string& additional_msg = "");

    /**
     * @brief 创建升级查询响应
     */
    std::vector<uint8_t> CreateUpgradeQueryResponse(const UniversalParsedMessage& request_msg, bool has_upgrade = false);

    /**
     * @brief 创建升级推送消息
     * @param device_unique_id 设备唯一ID
     * @param seq_num 序列号
     * @param upgrade_task 从数据库查询到的完整升级任务信息
     * @param ftp_config FTP服务器的认证信息
     * @param protocol_id 协议ID，用于确定响应格式
     * @return 响应数据
     */
    std::vector<uint8_t> CreateUpgradePushMessage(const std::string& device_unique_id, uint16_t seq_num,
                                                  const DPower::DB::DPowerUpgradeTask& upgrade_task,
                                                  const ParserConfig::FtpConfig& ftp_config,
                                                  const std::string& protocol_id = "dp_protocol_v1");

    /**
     * @brief 创建参数下发消息
     */
    std::vector<uint8_t> CreateParameterDownloadMessage(const std::string& device_unique_id, uint16_t seq_num,
                                                        uint8_t param_count, const std::string& protocol_id = "dp_protocol_v1");

    /**
     * @brief 根据请求消息自动创建响应
     */
    std::vector<uint8_t> CreateAutoResponse(const UniversalParsedMessage& request_msg);

    /**
     * @brief 设置心跳参数
     */
    void SetHeartbeatParams(uint8_t heart_interval, uint8_t keep_connect);

    /**
     * @brief 设置升级参数
     */
    void SetUpgradeInfo(const DPower::DB::DPowerUpgradeTask& upgrade_info);

    /**
     * @brief 设置FTP配置
     */
    void SetFtpConfig(const ParserConfig::FtpConfig& ftp_config);

    /**
     * @brief 设置认证生成器
     */
    void SetAuthGenerator(std::shared_ptr<DPower::Utils::DPowerAuthGenerator> generator);

    /**
     * @brief 设置认证密钥
     */
    void SetAuthSecret(const std::string& secret);

    /**
     * @brief Base64编码
     */
    std::string Base64Encode(const std::vector<uint8_t>& data) const;

private:
    // 成员变量
    std::shared_ptr<IUniversalParser> universal_parser_;
    std::shared_ptr<MultiProtocolManager> protocol_manager_;
    uint8_t heart_interval_;
    uint8_t keep_connect_;
    DPower::DB::DPowerUpgradeTask upgrade_info_;
    ParserConfig::FtpConfig ftp_config_;
    std::shared_ptr<DPower::Utils::DPowerAuthGenerator> auth_generator_;
    std::string auth_secret_;

    // 私有方法
    std::vector<uint8_t> GenerateAuthenticationCode(const std::string& device_unique_id) const;
    std::vector<uint8_t> CreateHeader(uint16_t msg_id, uint16_t body_size, const std::string& device_unique_id, 
                                     uint16_t seq_num, const std::string& protocol_id = "dp_protocol_v1") const;
    std::vector<uint8_t> CreateBody(uint16_t msg_id, const std::map<std::string, std::vector<uint8_t>>& body_data,
                                   const std::string& protocol_id = "dp_protocol_v1",
                                   const BodyBuildContext* ctx = nullptr) const;
    std::vector<uint8_t> AddCRCAndTail(const std::vector<uint8_t>& packet, const std::string& protocol_id = "dp_protocol_v1") const;
    std::vector<uint8_t> PackValue(uint32_t value, size_t size) const;
    std::vector<uint8_t> PackScheduleDateTime(const std::chrono::system_clock::time_point& date_point,
                                              float time_value) const;
    std::vector<uint8_t> PackString(const std::string& str, size_t size) const;
    std::string ExtractDeviceUniqueId(const UniversalParsedMessage& msg) const;
    uint16_t ExtractSequenceNumber(const UniversalParsedMessage& msg) const;
    std::vector<uint8_t> GetCurrentTimeBCD() const;
};

#pragma once

#include <string>
#include "logic/UniversalParser.h"

/**
 * @brief 升级结果上报结果
 */
struct UpgradeResultReportResult {
    bool success;
    std::string error_message;
    uint8_t result_code; // 0x00-成功, 0x01-失败
};

/**
 * @brief 升级服务接口
 * 抽象升级相关的业务逻辑
 */
class UpgradeService {
public:
    virtual ~UpgradeService() = default;
    
    /**
     * @brief 处理升级结果上报
     * @param parsed_msg 解析后的消息
     * @return 处理结果
     */
    virtual UpgradeResultReportResult ProcessUpgradeResultReport(const UniversalParsedMessage& parsed_msg) = 0;
}; 
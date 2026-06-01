#pragma once

#include <string>
#include "logic/UniversalParser.h"

/**
 * @brief 故障上报结果
 */
struct FaultReportResult {
    bool success;
    std::string error_message;
    uint8_t result_code; // 0x00-成功, 0x01-失败
};

/**
 * @brief 故障服务接口
 * 抽象故障相关的业务逻辑
 */
class FaultService {
public:
    virtual ~FaultService() = default;
    
    /**
     * @brief 处理故障上报
     * @param parsed_msg 解析后的消息
     * @return 处理结果
     */
    virtual FaultReportResult ProcessFaultReport(const UniversalParsedMessage& parsed_msg) = 0;
}; 
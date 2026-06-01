#pragma once

#include <string>
#include "logic/UniversalParser.h"

/**
 * @brief 点钞上报结果
 */
struct BanknoteReportResult {
    bool success;
    std::string error_message;
    uint8_t result_code; // 0x00-成功, 0x01-失败
};

/**
 * @brief 点钞服务接口
 * 抽象点钞相关的业务逻辑
 */
class BanknoteService {
public:
    virtual ~BanknoteService() = default;
    
    /**
     * @brief 处理点钞信息上报
     * @param parsed_msg 解析后的消息
     * @return 处理结果
     */
    virtual BanknoteReportResult ProcessBanknoteReport(const UniversalParsedMessage& parsed_msg) = 0;
}; 
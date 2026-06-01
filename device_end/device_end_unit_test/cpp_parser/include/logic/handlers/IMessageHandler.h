#pragma once

#include <vector>
#include <memory>
#include "logic/UniversalParser.h"

/**
 * @brief 消息处理器接口
 * 使用策略模式，每个消息类型对应一个处理器
 */
class IMessageHandler {
public:
    virtual ~IMessageHandler() = default;
    
    /**
     * @brief 处理消息
     * @param parsed_msg 解析后的消息
     * @return 响应数据
     */
    virtual std::vector<uint8_t> Handle(const UniversalParsedMessage& parsed_msg) = 0;
    
    /**
     * @brief 检查是否可以处理指定消息类型
     * @param msg_id 消息ID
     * @return 是否可以处理
     */
    virtual bool CanHandle(uint16_t msg_id) const = 0;
    
    /**
     * @brief 获取处理器名称（用于日志和调试）
     * @return 处理器名称
     */
    virtual std::string GetHandlerName() const = 0;
}; 
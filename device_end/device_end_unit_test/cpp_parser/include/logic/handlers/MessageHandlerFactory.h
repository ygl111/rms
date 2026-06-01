#pragma once

#include "logic/handlers/IMessageHandler.h"
#include "logic/services/DeviceService.h"
#include "logic/services/BanknoteService.h"
#include "logic/services/FaultService.h"
#include "logic/services/UpgradeService.h"
#include "logic/ResponseGenerator.h"
#include <memory>
#include <unordered_map>

/**
 * @brief 消息处理器工厂
 * 使用工厂模式管理所有消息处理器
 */
class MessageHandlerFactory {
public:
    MessageHandlerFactory(
        std::shared_ptr<DeviceService> device_service,
        std::shared_ptr<BanknoteService> banknote_service,
        std::shared_ptr<FaultService> fault_service,
        std::shared_ptr<UpgradeService> upgrade_service,
        std::shared_ptr<ResponseGenerator> response_generator
    );

    /**
     * @brief 获取指定消息类型的处理器
     * @param msg_id 消息ID
     * @return 消息处理器指针，如果不存在则返回nullptr
     */
    IMessageHandler* GetHandler(uint16_t msg_id);

    /**
     * @brief 检查是否支持指定消息类型
     * @param msg_id 消息ID
     * @return 是否支持
     */
    bool IsSupported(uint16_t msg_id) const;

    /**
     * @brief 获取支持的消息类型列表
     * @return 支持的消息ID列表
     */
    std::vector<uint16_t> GetSupportedMessageTypes() const;

private:
    std::unordered_map<uint16_t, std::unique_ptr<IMessageHandler>> handlers_;
}; 
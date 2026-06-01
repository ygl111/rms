#pragma once

#include "logic/handlers/IMessageHandler.h"
#include "logic/services/DeviceService.h"
#include "logic/ResponseGenerator.h"
#include <memory>

/**
 * @brief 设备注册消息处理器
 */
class RegistrationHandler : public IMessageHandler {
public:
    RegistrationHandler(
        std::shared_ptr<DeviceService> device_service,
        std::shared_ptr<ResponseGenerator> response_generator
    );

    std::vector<uint8_t> Handle(const UniversalParsedMessage& parsed_msg) override;
    bool CanHandle(uint16_t msg_id) const override;
    std::string GetHandlerName() const override;

private:
    std::shared_ptr<DeviceService> device_service_;
    std::shared_ptr<ResponseGenerator> response_generator_;
}; 
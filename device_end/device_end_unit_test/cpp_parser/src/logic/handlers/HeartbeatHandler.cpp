#include "logic/handlers/HeartbeatHandler.h"

HeartbeatHandler::HeartbeatHandler(
    std::shared_ptr<DeviceService> device_service,
    std::shared_ptr<ResponseGenerator> response_generator)
    : device_service_(std::move(device_service)),
      response_generator_(std::move(response_generator))
{
}

std::vector<uint8_t> HeartbeatHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    return device_service_->ProcessHeartbeat(parsed_msg);
}

bool HeartbeatHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 4; // 心跳
}

std::string HeartbeatHandler::GetHandlerName() const {
    return "HeartbeatHandler";
} 
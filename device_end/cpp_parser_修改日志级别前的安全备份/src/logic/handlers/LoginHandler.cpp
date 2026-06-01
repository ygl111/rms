#include "logic/handlers/LoginHandler.h"

LoginHandler::LoginHandler(
    std::shared_ptr<DeviceService> device_service,
    std::shared_ptr<ResponseGenerator> response_generator)
    : device_service_(std::move(device_service)),
      response_generator_(std::move(response_generator))
{
}

std::vector<uint8_t> LoginHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    auto result = device_service_->LoginDevice(parsed_msg);
    return response_generator_->CreateLoginResponse(parsed_msg, result.result_code, result.keep_connect);
}

bool LoginHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 3; // 终端登录
}

std::string LoginHandler::GetHandlerName() const {
    return "LoginHandler";
} 
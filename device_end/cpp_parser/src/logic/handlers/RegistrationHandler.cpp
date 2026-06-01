#include "logic/handlers/RegistrationHandler.h"
#include "logic/utils/Logger.h"
#include <iomanip>
#include <sstream>

RegistrationHandler::RegistrationHandler(
    std::shared_ptr<DeviceService> device_service,
    std::shared_ptr<ResponseGenerator> response_generator)
    : device_service_(std::move(device_service)),
      response_generator_(std::move(response_generator))
{
}

std::vector<uint8_t> RegistrationHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    auto result = device_service_->RegisterDevice(parsed_msg);
    std::ostringstream oss;
    oss << std::uppercase << std::hex << std::setw(2) << std::setfill('0')
        << static_cast<unsigned int>(result.result_code);
    Utils::Logger::Instance().Log(
        "DEBUG",
        "result_code=0x" + oss.str() +
            " auth_len=" + std::to_string(result.auth_code.size()),
        "RegistrationHandler");
    return response_generator_->CreateRegistrationResponse(parsed_msg, result.result_code, result.auth_code);
}

bool RegistrationHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 2; // 终端注册
}

std::string RegistrationHandler::GetHandlerName() const {
    return "RegistrationHandler";
} 
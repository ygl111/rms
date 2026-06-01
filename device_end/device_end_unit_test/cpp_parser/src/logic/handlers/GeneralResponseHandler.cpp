#include "logic/handlers/GeneralResponseHandler.h"
#include "logic/utils/MessageUtils.h"
#include <iostream>
#include "logic/utils/Logger.h"

GeneralResponseHandler::GeneralResponseHandler(std::shared_ptr<DeviceService> device_service, 
                                             std::shared_ptr<ResponseGenerator> response_generator)
    : device_service_(device_service), response_generator_(response_generator) {
}

std::vector<uint8_t> GeneralResponseHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    // 设备通用应答报文不需要任何处理，只打印成功处理的消息
    Utils::Logger::Instance().Log("INFO", "Successfully processed device general response message", "GeneralResponseHandler");
    
    // 返回空的响应，因为这是设备发送的应答报文，不需要系统回复
    return std::vector<uint8_t>();
}

bool GeneralResponseHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 1;  // 处理设备通用应答报文
}

std::string GeneralResponseHandler::GetHandlerName() const {
    return "GeneralResponseHandler";
} 
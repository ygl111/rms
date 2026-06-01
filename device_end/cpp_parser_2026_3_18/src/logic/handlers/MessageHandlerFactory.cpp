#include "logic/handlers/MessageHandlerFactory.h"
#include "logic/handlers/RegistrationHandler.h"
#include "logic/handlers/LoginHandler.h"
#include "logic/handlers/HeartbeatHandler.h"
#include "logic/handlers/FaultReportHandler.h"
#include "logic/handlers/BanknoteReportHandler.h"
#include "logic/handlers/UpgradeResultHandler.h"
#include "logic/handlers/GeneralResponseHandler.h"

MessageHandlerFactory::MessageHandlerFactory(
    std::shared_ptr<DeviceService> device_service,
    std::shared_ptr<BanknoteService> banknote_service,
    std::shared_ptr<FaultService> fault_service,
    std::shared_ptr<UpgradeService> upgrade_service,
    std::shared_ptr<ResponseGenerator> response_generator)
{
    // 注册所有消息处理器
    handlers_[1] = std::make_unique<GeneralResponseHandler>(device_service, response_generator);
    handlers_[2] = std::make_unique<RegistrationHandler>(device_service, response_generator);
    handlers_[3] = std::make_unique<LoginHandler>(device_service, response_generator);
    handlers_[4] = std::make_unique<HeartbeatHandler>(device_service, response_generator);
    handlers_[10] = std::make_unique<FaultReportHandler>(fault_service, response_generator);
    handlers_[12] = std::make_unique<BanknoteReportHandler>(banknote_service, response_generator);
    handlers_[6] = std::make_unique<UpgradeResultHandler>(upgrade_service, response_generator);
}

IMessageHandler* MessageHandlerFactory::GetHandler(uint16_t msg_id) {
    auto it = handlers_.find(msg_id);
    return it != handlers_.end() ? it->second.get() : nullptr;
}

bool MessageHandlerFactory::IsSupported(uint16_t msg_id) const {
    return handlers_.find(msg_id) != handlers_.end();
}

std::vector<uint16_t> MessageHandlerFactory::GetSupportedMessageTypes() const {
    std::vector<uint16_t> supported_types;
    for (const auto& [msg_id, _] : handlers_) {
        supported_types.push_back(msg_id);
    }
    return supported_types;
} 
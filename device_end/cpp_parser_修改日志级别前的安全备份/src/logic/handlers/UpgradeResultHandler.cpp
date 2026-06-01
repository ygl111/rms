#include "logic/handlers/UpgradeResultHandler.h"

UpgradeResultHandler::UpgradeResultHandler(
    std::shared_ptr<UpgradeService> upgrade_service,
    std::shared_ptr<ResponseGenerator> response_generator)
    : upgrade_service_(std::move(upgrade_service)),
      response_generator_(std::move(response_generator))
{
}

std::vector<uint8_t> UpgradeResultHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    auto result = upgrade_service_->ProcessUpgradeResultReport(parsed_msg);
    return response_generator_->CreateGenericResponse(parsed_msg, result.result_code);
}

bool UpgradeResultHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 6; // 升级结果上报
}

std::string UpgradeResultHandler::GetHandlerName() const {
    return "UpgradeResultHandler";
} 
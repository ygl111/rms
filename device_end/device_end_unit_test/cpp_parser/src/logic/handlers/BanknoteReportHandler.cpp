#include "logic/handlers/BanknoteReportHandler.h"

BanknoteReportHandler::BanknoteReportHandler(
    std::shared_ptr<BanknoteService> banknote_service,
    std::shared_ptr<ResponseGenerator> response_generator)
    : banknote_service_(std::move(banknote_service)),
      response_generator_(std::move(response_generator))
{
}

std::vector<uint8_t> BanknoteReportHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    auto result = banknote_service_->ProcessBanknoteReport(parsed_msg);
    return response_generator_->CreateGenericResponse(parsed_msg, result.result_code);
}

bool BanknoteReportHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 12; // 点钞上报
}

std::string BanknoteReportHandler::GetHandlerName() const {
    return "BanknoteReportHandler";
} 
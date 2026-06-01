#include "logic/handlers/FaultReportHandler.h"

FaultReportHandler::FaultReportHandler(
    std::shared_ptr<FaultService> fault_service,
    std::shared_ptr<ResponseGenerator> response_generator)
    : fault_service_(std::move(fault_service)),
      response_generator_(std::move(response_generator))
{
}

std::vector<uint8_t> FaultReportHandler::Handle(const UniversalParsedMessage& parsed_msg) {
    auto result = fault_service_->ProcessFaultReport(parsed_msg);
    return response_generator_->CreateGenericResponse(parsed_msg, result.result_code);
}

bool FaultReportHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 10; // 设备故障上报
}

std::string FaultReportHandler::GetHandlerName() const {
    return "FaultReportHandler";
} 
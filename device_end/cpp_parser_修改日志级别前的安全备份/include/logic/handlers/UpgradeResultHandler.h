#pragma once
#include "logic/handlers/IMessageHandler.h"
#include "logic/services/UpgradeService.h"
#include "logic/ResponseGenerator.h"
#include <memory>

class UpgradeResultHandler : public IMessageHandler {
public:
    UpgradeResultHandler(std::shared_ptr<UpgradeService> upgrade_service, 
                         std::shared_ptr<ResponseGenerator> response_generator);
    
    std::vector<uint8_t> Handle(const UniversalParsedMessage& parsed_msg) override;
    bool CanHandle(uint16_t msg_id) const override;
    std::string GetHandlerName() const override;
    
private:
    std::shared_ptr<UpgradeService> upgrade_service_;
    std::shared_ptr<ResponseGenerator> response_generator_;
}; 
#pragma once

#include <memory>
#include <string>

namespace DPower {
namespace MQ {

struct DPowerMqResult {
    bool success { false };
    std::string error_message;
};

class DPowerMqClient {
public:
    virtual ~DPowerMqClient() = default;

    virtual DPowerMqResult Connect(const std::string& connection_uri) = 0;
    virtual void Disconnect() = 0;
    virtual bool IsConnected() const = 0;
    virtual DPowerMqResult Publish(const std::string& queue_name,
                                   const std::string& payload,
                                   bool persistent = true) = 0;
};

class DPowerMqFactory {
public:
    virtual ~DPowerMqFactory() = default;
    virtual std::unique_ptr<DPowerMqClient> Create() = 0;
};

std::unique_ptr<DPowerMqFactory> CreateRabbitMqFactory();

} // namespace MQ
} // namespace DPower

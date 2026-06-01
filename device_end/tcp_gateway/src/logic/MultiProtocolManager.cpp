#include "logic/MultiProtocolManager.h"
#include <fstream>
#include "logic/utils/Logger.h"

MultiProtocolManager::MultiProtocolManager() {
}

bool MultiProtocolManager::LoadProtocolConfig(const std::string& config_file) {
    try {
        std::ifstream file(config_file);
        if (!file.is_open()) {
            Utils::Logger::Instance().Log("ERROR", "Failed to open protocol config file: " + config_file, "MultiProtocolManager");
            return false;
        }
        
        file >> protocol_registry_;
        file.close();
        
        // 构建端口到协议的映射
        port_to_protocol_.clear();
        protocol_configs_.clear();
        
        for (const auto& [protocol_id, config] : protocol_registry_["protocols"].items()) {
            int port = config["port"];
            port_to_protocol_[port] = protocol_id;
            protocol_configs_[protocol_id] = config;
        }
        
        Utils::Logger::Instance().Log("INFO", "Loaded " + std::to_string(protocol_configs_.size()) + " protocols", "MultiProtocolManager");
        return true;
        
    } catch (const std::exception& e) {
        Utils::Logger::Instance().Log("ERROR", std::string("Error loading protocol config: ") + e.what(), "MultiProtocolManager");
        return false;
    }
}

std::unique_ptr<IProtocolIdentifier> MultiProtocolManager::GetIdentifierByPort(int port) {
    auto it = port_to_protocol_.find(port);
    if (it == port_to_protocol_.end()) {
        return nullptr;
    }
    
    return GetIdentifierById(it->second);
}

std::unique_ptr<IProtocolIdentifier> MultiProtocolManager::GetIdentifierById(const std::string& protocol_id) {
    auto it = protocol_configs_.find(protocol_id);
    if (it == protocol_configs_.end()) {
        return nullptr;
    }
    
    return ProtocolIdentifierFactory::CreateIdentifier(protocol_id, it->second);
}

ProtocolIdentificationResult MultiProtocolManager::IdentifyProtocol(const std::vector<uint8_t>& data, int port) {
    auto identifier = GetIdentifierByPort(port);
    if (!identifier) {
        ProtocolIdentificationResult result;
        result.is_valid = false;
        result.error_message = "Unsupported port: " + std::to_string(port);
        return result;
    }
    
    return identifier->IdentifyProtocol(data);
}

std::vector<int> MultiProtocolManager::GetSupportedPorts() const {
    std::vector<int> ports;
    for (const auto& [port, _] : port_to_protocol_) {
        ports.push_back(port);
    }
    return ports;
} 
#include "logic/MultiProtocolManager.h"
#include <fstream>
#include <iostream>

MultiProtocolManager::MultiProtocolManager() {
}

bool MultiProtocolManager::LoadProtocolConfig(const std::string& config_file) {
    try {
        std::ifstream file(config_file);
        if (!file.is_open()) {
            std::cerr << "Failed to open protocol config file: " << config_file << std::endl;
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
        
        std::cout << "Loaded " << protocol_configs_.size() << " protocols" << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Error loading protocol config: " << e.what() << std::endl;
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
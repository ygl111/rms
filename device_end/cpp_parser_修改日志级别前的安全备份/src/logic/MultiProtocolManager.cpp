#include "logic/MultiProtocolManager.h"
#include <fstream>
#include <iostream>
#include <filesystem>

MultiProtocolManager::MultiProtocolManager() {
}

bool MultiProtocolManager::LoadProtocolRegistry(const std::string& registry_file) {
    try {
        std::ifstream file(registry_file);
        if (!file.is_open()) {
            std::cerr << "Failed to open protocol registry file: " << registry_file << std::endl;
            return false;
        }
        
        file >> protocol_registry_;
        file.close();
        
        // 获取配置目录和默认协议
        config_directory_ = protocol_registry_["config_directory"];
        default_protocol_ = protocol_registry_["default_protocol"];
        
        // 加载所有协议的配置
        for (const auto& [protocol_id, protocol_info] : protocol_registry_["protocols"].items()) {
            std::string config_file = protocol_info["config_file"];
            std::string full_path = config_directory_ + "/" + config_file;
            
            if (!LoadProtocolConfig(protocol_id, full_path)) {
                std::cerr << "Failed to load config for protocol: " << protocol_id << std::endl;
                return false;
            }
        }
        
        std::cout << "Loaded " << protocol_configs_.size() << " protocol configurations" << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Error loading protocol registry: " << e.what() << std::endl;
        return false;
    }
}

bool MultiProtocolManager::LoadProtocolConfig(const std::string& protocol_id, const std::string& config_file) {
    try {
        std::ifstream file(config_file);
        if (!file.is_open()) {
            std::cerr << "Failed to open protocol config file: " << config_file << std::endl;
            return false;
        }
        
        json config;
        file >> config;
        file.close();
        
        protocol_configs_[protocol_id] = config;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Error loading protocol config " << config_file << ": " << e.what() << std::endl;
        return false;
    }
}

json MultiProtocolManager::GetProtocolConfig(const std::string& protocol_id) const {
    auto it = protocol_configs_.find(protocol_id);
    if (it == protocol_configs_.end()) {
        std::cerr << "Protocol not found: " << protocol_id << std::endl;
        return json();
    }
    
    return it->second;
}

json MultiProtocolManager::GetProtocolConfigByName(const std::string& name, const std::string& version) const {
    // 查找匹配的协议ID
    for (const auto& [protocol_id, protocol_info] : protocol_registry_["protocols"].items()) {
        if (protocol_info["name"] == name && protocol_info["version"] == version) {
            return GetProtocolConfig(protocol_id);
        }
    }
    
    std::cerr << "Protocol not found: " << name << " v" << version << std::endl;
    return json();
}

std::vector<std::string> MultiProtocolManager::GetSupportedProtocols() const {
    std::vector<std::string> protocols;
    for (const auto& [protocol_id, _] : protocol_configs_) {
        protocols.push_back(protocol_id);
    }
    return protocols;
}

json MultiProtocolManager::GetProtocolInfo(const std::string& protocol_id) const {
    auto it = protocol_registry_["protocols"].find(protocol_id);
    if (it != protocol_registry_["protocols"].end()) {
        return it.value();
    }
    return json();
}

bool MultiProtocolManager::IsProtocolSupported(const std::string& protocol_id) const {
    return protocol_configs_.find(protocol_id) != protocol_configs_.end();
} 
#include "logic/MultiProtocolManager.h"
#include <fstream>
#include <iostream>
#include <filesystem>
#include "logic/utils/Logger.h"

MultiProtocolManager::MultiProtocolManager() {
}

bool MultiProtocolManager::LoadProtocolRegistry(const std::string& registry_file) {
    try {
        std::ifstream file(registry_file);
        if (!file.is_open()) {
            Utils::Logger::Instance().Log("ERROR", std::string("Failed to open protocol registry file: ") + registry_file, "MultiProtocolManager");
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
                Utils::Logger::Instance().Log("ERROR", std::string("Failed to load config for protocol: ") + protocol_id, "MultiProtocolManager");
                return false;
            }
        }
        
        Utils::Logger::Instance().Log("INFO", std::string("Loaded ") + std::to_string(protocol_configs_.size()) + " protocol configurations", "MultiProtocolManager");
        return true;
        
    } catch (const std::exception& e) {
        Utils::Logger::Instance().Log("ERROR", std::string("Error loading protocol registry: ") + e.what(), "MultiProtocolManager");
        return false;
    }
}

bool MultiProtocolManager::LoadProtocolConfig(const std::string& protocol_id, const std::string& config_file) {
    try {
        std::ifstream file(config_file);
        if (!file.is_open()) {
            Utils::Logger::Instance().Log("ERROR", std::string("Failed to open protocol config file: ") + config_file, "MultiProtocolManager");
            return false;
        }
        
        json config;
        file >> config;
        file.close();
        
        protocol_configs_[protocol_id] = config;
        return true;
        
    } catch (const std::exception& e) {
        Utils::Logger::Instance().Log("ERROR", std::string("Error loading protocol config ") + config_file + ": " + e.what(), "MultiProtocolManager");
        return false;
    }
}

json MultiProtocolManager::GetProtocolConfig(const std::string& protocol_id) const {
    auto it = protocol_configs_.find(protocol_id);
    if (it == protocol_configs_.end()) {
        Utils::Logger::Instance().Log("WARN", std::string("Protocol not found: ") + protocol_id, "MultiProtocolManager");
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
    
    Utils::Logger::Instance().Log("WARN", std::string("Protocol not found: ") + name + " v" + version, "MultiProtocolManager");
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
#pragma once

#include "logic/ProtocolIdentifier.h"
#include <map>
#include <memory>
#include <string>
#include <json.hpp>

using json = nlohmann::json;

// 多协议管理器
class MultiProtocolManager {
public:
    MultiProtocolManager();
    ~MultiProtocolManager() = default;
    
    // 加载协议配置
    bool LoadProtocolConfig(const std::string& config_file);
    
    // 根据端口获取协议识别器
    std::unique_ptr<IProtocolIdentifier> GetIdentifierByPort(int port);
    
    // 根据协议ID获取协议识别器
    std::unique_ptr<IProtocolIdentifier> GetIdentifierById(const std::string& protocol_id);
    
    // 识别协议类型
    ProtocolIdentificationResult IdentifyProtocol(const std::vector<uint8_t>& data, int port);
    
    // 获取所有支持的端口
    std::vector<int> GetSupportedPorts() const;
    
    // 获取协议配置
    const json& GetProtocolRegistry() const { return protocol_registry_; }
    
private:
    json protocol_registry_;
    std::map<int, std::string> port_to_protocol_;
    std::map<std::string, json> protocol_configs_;
}; 
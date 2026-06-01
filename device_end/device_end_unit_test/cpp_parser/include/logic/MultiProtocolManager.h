#pragma once

#include <string>
#include <map>
#include <memory>
#include <json.hpp>

using json = nlohmann::json;

// 多协议管理器 - 负责管理不同协议的解析器
class MultiProtocolManager {
public:
    MultiProtocolManager();
    ~MultiProtocolManager() = default;
    
    // 加载协议注册表
    bool LoadProtocolRegistry(const std::string& registry_file);
    
    // 根据协议ID获取协议配置
    json GetProtocolConfig(const std::string& protocol_id) const;
    
    // 根据协议名称和版本获取协议配置
    json GetProtocolConfigByName(const std::string& name, const std::string& version) const;
    
    // 获取支持的协议列表
    std::vector<std::string> GetSupportedProtocols() const;
    
    // 获取协议信息
    json GetProtocolInfo(const std::string& protocol_id) const;
    
    // 获取默认协议ID
    std::string GetDefaultProtocol() const { return default_protocol_; }
    
    // 检查协议是否支持
    bool IsProtocolSupported(const std::string& protocol_id) const;
    
private:
    // 加载单个协议配置
    bool LoadProtocolConfig(const std::string& protocol_id, const std::string& config_file);
    
    json protocol_registry_;
    std::map<std::string, json> protocol_configs_;
    std::string default_protocol_;
    std::string config_directory_;
}; 
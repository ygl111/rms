#include "dpower/config/Interfaces.h"
#include <json.hpp>
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>

using json = nlohmann::json;

namespace DPower {
namespace Config {

//---------------------------------------------
// JsonConfigManager 实现
//---------------------------------------------
class JsonConfigManager : public DPowerConfigManager {
public:
    JsonConfigManager() : modified_(false) {}

    ~JsonConfigManager() override = default;

    // 配置加载和保存
    bool LoadFromFile(const std::string& file_path) override {
        try {
            std::ifstream file(file_path);
            if (!file.is_open()) {
                return false;
            }

            std::stringstream buffer;
            buffer << file.rdbuf();
            return LoadFromString(buffer.str());
        } catch (const std::exception& e) {
            std::cerr << "Failed to load config from file: " << e.what() << std::endl;
            return false;
        }
    }

    bool LoadFromString(const std::string& config_data) override {
        try {
            config_json_ = json::parse(config_data);
            modified_ = false;
            return true;
        } catch (const json::exception& e) {
            std::cerr << "Failed to parse JSON config: " << e.what() << std::endl;
            return false;
        }
    }

    bool SaveToFile(const std::string& file_path) const override {
        try {
            std::ofstream file(file_path);
            if (!file.is_open()) {
                return false;
            }

            file << SaveToString();
            return true;
        } catch (const std::exception& e) {
            std::cerr << "Failed to save config to file: " << e.what() << std::endl;
            return false;
        }
    }

    std::string SaveToString() const override {
        try {
            return config_json_.dump(2); // 美化输出，缩进2个空格
        } catch (const json::exception& e) {
            std::cerr << "Failed to serialize JSON config: " << e.what() << std::endl;
            return "{}";
        }
    }

    // 配置项操作
    bool SetValue(const std::string& key, const std::string& value) override {
        try {
            // 支持嵌套键，如 "redis.host"
            std::vector<std::string> key_parts = SplitKey(key);
            json* current = &config_json_;
            
            // 导航到父节点
            for (size_t i = 0; i < key_parts.size() - 1; ++i) {
                if (!current->contains(key_parts[i])) {
                    (*current)[key_parts[i]] = json::object();
                }
                current = &(*current)[key_parts[i]];
            }
            
            // 设置值
            (*current)[key_parts.back()] = value;
            modified_ = true;
            
            // 触发变更回调
            if (change_callback_) {
                change_callback_(key, value);
            }
            
            return true;
        } catch (const json::exception& e) {
            std::cerr << "Failed to set config value: " << e.what() << std::endl;
            return false;
        }
    }

    std::string GetValue(const std::string& key, const std::string& default_value) const override {
        try {
            std::vector<std::string> key_parts = SplitKey(key);
            const json* current = &config_json_;
            
            // 导航到目标节点
            for (const auto& part : key_parts) {
                if (!current->contains(part)) {
                    return default_value;
                }
                current = &(*current)[part];
            }
            
            if (current->is_string()) {
                return current->get<std::string>();
            } else {
                return current->dump();
            }
        } catch (const json::exception& e) {
            std::cerr << "Failed to get config value: " << e.what() << std::endl;
            return default_value;
        }
    }

    bool HasKey(const std::string& key) const override {
        try {
            std::vector<std::string> key_parts = SplitKey(key);
            const json* current = &config_json_;
            
            for (const auto& part : key_parts) {
                if (!current->contains(part)) {
                    return false;
                }
                current = &(*current)[part];
            }
            
            return true;
        } catch (const json::exception& e) {
            return false;
        }
    }

    bool RemoveKey(const std::string& key) override {
        try {
            std::vector<std::string> key_parts = SplitKey(key);
            json* current = &config_json_;
            
            // 导航到父节点
            for (size_t i = 0; i < key_parts.size() - 1; ++i) {
                if (!current->contains(key_parts[i])) {
                    return false;
                }
                current = &(*current)[key_parts[i]];
            }
            
            // 删除键
            if (current->contains(key_parts.back())) {
                current->erase(key_parts.back());
                modified_ = true;
                return true;
            }
            
            return false;
        } catch (const json::exception& e) {
            std::cerr << "Failed to remove config key: " << e.what() << std::endl;
            return false;
        }
    }

    // 类型化获取方法
    int GetInt(const std::string& key, int default_value) const override {
        try {
            std::string value = GetValue(key, "");
            if (value.empty()) return default_value;
            
            if (config_json_.contains(key) && config_json_[key].is_number()) {
                return config_json_[key].get<int>();
            }
            
            return std::stoi(value);
        } catch (const std::exception& e) {
            return default_value;
        }
    }

    double GetDouble(const std::string& key, double default_value) const override {
        try {
            std::string value = GetValue(key, "");
            if (value.empty()) return default_value;
            
            if (config_json_.contains(key) && config_json_[key].is_number()) {
                return config_json_[key].get<double>();
            }
            
            return std::stod(value);
        } catch (const std::exception& e) {
            return default_value;
        }
    }

    bool GetBool(const std::string& key, bool default_value) const override {
        try {
            std::string value = GetValue(key, "");
            if (value.empty()) return default_value;
            
            if (config_json_.contains(key) && config_json_[key].is_boolean()) {
                return config_json_[key].get<bool>();
            }
            
            std::transform(value.begin(), value.end(), value.begin(), ::tolower);
            return (value == "true" || value == "1" || value == "yes");
        } catch (const std::exception& e) {
            return default_value;
        }
    }

    std::vector<std::string> GetArray(const std::string& key) const override {
        std::vector<std::string> result;
        try {
            std::vector<std::string> key_parts = SplitKey(key);
            const json* current = &config_json_;
            
            for (const auto& part : key_parts) {
                if (!current->contains(part)) {
                    return result;
                }
                current = &(*current)[part];
            }
            
            if (current->is_array()) {
                for (const auto& item : *current) {
                    if (item.is_string()) {
                        result.push_back(item.get<std::string>());
                    } else {
                        result.push_back(item.dump());
                    }
                }
            }
        } catch (const json::exception& e) {
            std::cerr << "Failed to get config array: " << e.what() << std::endl;
        }
        
        return result;
    }

    // 配置验证
    DPowerConfigValidationResult Validate() const override {
        DPowerConfigValidationResult result;
        result.valid = true;
        
        if (schema_.empty()) {
            return result; // 没有schema，认为有效
        }
        
        for (const auto& schema_item : schema_) {
            const std::string& key = schema_item.first;
            const DPowerConfigItem& item = schema_item.second;
            
            if (!HasKey(key)) {
                if (item.required) {
                    result.valid = false;
                    result.errors.push_back("Required key missing: " + key);
                }
                continue;
            }
            
            // 类型验证（简化实现）
            std::string value = GetValue(key, "");
            if (item.type == DPowerConfigType::Integer) {
                try {
                    std::stoi(value);
                } catch (...) {
                    result.valid = false;
                    result.errors.push_back("Invalid integer value for key: " + key);
                }
            } else if (item.type == DPowerConfigType::Double) {
                try {
                    std::stod(value);
                } catch (...) {
                    result.valid = false;
                    result.errors.push_back("Invalid double value for key: " + key);
                }
            } else if (item.type == DPowerConfigType::Boolean) {
                std::transform(value.begin(), value.end(), value.begin(), ::tolower);
                if (value != "true" && value != "false" && value != "1" && value != "0") {
                    result.valid = false;
                    result.errors.push_back("Invalid boolean value for key: " + key);
                }
            }
        }
        
        return result;
    }

    void SetSchema(const std::map<std::string, DPowerConfigItem>& schema) override {
        schema_ = schema;
    }

    // 配置监听
    void SetChangeCallback(std::function<void(const std::string&, const std::string&)> callback) override {
        change_callback_ = callback;
    }

    void ClearChangeCallback() override {
        change_callback_ = nullptr;
    }

    // 配置信息
    std::vector<std::string> GetAllKeys() const override {
        std::vector<std::string> keys;
        CollectKeys(config_json_, "", keys);
        return keys;
    }

    std::map<std::string, std::string> GetAllValues() const override {
        std::map<std::string, std::string> values;
        CollectValues(config_json_, "", values);
        return values;
    }

    size_t GetConfigSize() const override {
        return config_json_.size();
    }

    // 配置重载
    bool Reload() override {
        // 简化实现，实际可能需要从文件重新加载
        modified_ = false;
        return true;
    }

    bool IsModified() const override {
        return modified_;
    }

private:
    json config_json_;
    std::map<std::string, DPowerConfigItem> schema_;
    std::function<void(const std::string&, const std::string&)> change_callback_;
    bool modified_;

    std::vector<std::string> SplitKey(const std::string& key) const {
        std::vector<std::string> parts;
        std::stringstream ss(key);
        std::string part;
        
        while (std::getline(ss, part, '.')) {
            parts.push_back(part);
        }
        
        return parts;
    }

    void CollectKeys(const json& j, const std::string& prefix, std::vector<std::string>& keys) const {
        for (auto it = j.begin(); it != j.end(); ++it) {
            std::string current_key = prefix.empty() ? it.key() : prefix + "." + it.key();
            
            if (it.value().is_object()) {
                CollectKeys(it.value(), current_key, keys);
            } else {
                keys.push_back(current_key);
            }
        }
    }

    void CollectValues(const json& j, const std::string& prefix, std::map<std::string, std::string>& values) const {
        for (auto it = j.begin(); it != j.end(); ++it) {
            std::string current_key = prefix.empty() ? it.key() : prefix + "." + it.key();
            
            if (it.value().is_object()) {
                CollectValues(it.value(), current_key, values);
            } else {
                values[current_key] = it.value().dump();
            }
        }
    }
};

//---------------------------------------------
// JsonConfigManagerFactory 实现
//---------------------------------------------
class JsonConfigManagerFactory : public DPowerConfigManagerFactory {
public:
    std::unique_ptr<DPowerConfigManager> Create() override {
        return std::make_unique<JsonConfigManager>();
    }
};

//---------------------------------------------
// 外部可见工厂函数
//---------------------------------------------
std::unique_ptr<DPowerConfigManagerFactory> CreateJsonConfigFactory() {
    return std::make_unique<JsonConfigManagerFactory>();
}

} // namespace Config
} // namespace DPower 
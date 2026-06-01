#pragma once
// ================================================================
//  DPower::Config 抽象接口
//  业务层仅依赖这些接口，实现可由 JSON / YAML / 数据库等替换
// ================================================================

#include <string>
#include <map>
#include <vector>
#include <memory>
#include <functional>

namespace DPower {
namespace Config {

//---------------------------------------------
// 配置项类型
//---------------------------------------------
enum class DPowerConfigType {
    String,
    Integer,
    Double,
    Boolean,
    Array,
    Object
};

//---------------------------------------------
// 配置项结构
//---------------------------------------------
struct DPowerConfigItem {
    std::string key;
    std::string value;
    DPowerConfigType type;
    std::string description;
    bool required;
    
    DPowerConfigItem() : type(DPowerConfigType::String), required(false) {}
    DPowerConfigItem(const std::string& k, const std::string& v, DPowerConfigType t = DPowerConfigType::String)
        : key(k), value(v), type(t), required(false) {}
};

//---------------------------------------------
// 配置验证结果
//---------------------------------------------
struct DPowerConfigValidationResult {
    bool valid { false };
    std::vector<std::string> errors;
    std::vector<std::string> warnings;
};

//---------------------------------------------
// 抽象配置管理器
//---------------------------------------------
class DPowerConfigManager {
public:
    virtual ~DPowerConfigManager() = default;

    // 配置加载和保存
    virtual bool LoadFromFile(const std::string& file_path) = 0;
    virtual bool LoadFromString(const std::string& config_data) = 0;
    virtual bool SaveToFile(const std::string& file_path) const = 0;
    virtual std::string SaveToString() const = 0;

    // 配置项操作
    virtual bool SetValue(const std::string& key, const std::string& value) = 0;
    virtual std::string GetValue(const std::string& key, const std::string& default_value = "") const = 0;
    virtual bool HasKey(const std::string& key) const = 0;
    virtual bool RemoveKey(const std::string& key) = 0;

    // 类型化获取方法
    virtual int GetInt(const std::string& key, int default_value = 0) const = 0;
    virtual double GetDouble(const std::string& key, double default_value = 0.0) const = 0;
    virtual bool GetBool(const std::string& key, bool default_value = false) const = 0;
    virtual std::vector<std::string> GetArray(const std::string& key) const = 0;

    // 配置验证
    virtual DPowerConfigValidationResult Validate() const = 0;
    virtual void SetSchema(const std::map<std::string, DPowerConfigItem>& schema) = 0;

    // 配置监听
    virtual void SetChangeCallback(std::function<void(const std::string&, const std::string&)> callback) = 0;
    virtual void ClearChangeCallback() = 0;

    // 配置信息
    virtual std::vector<std::string> GetAllKeys() const = 0;
    virtual std::map<std::string, std::string> GetAllValues() const = 0;
    virtual size_t GetConfigSize() const = 0;

    // 配置重载
    virtual bool Reload() = 0;
    virtual bool IsModified() const = 0;
};

//---------------------------------------------
// 工厂
//---------------------------------------------
class DPowerConfigManagerFactory {
public:
    virtual std::unique_ptr<DPowerConfigManager> Create() = 0;
    virtual ~DPowerConfigManagerFactory() = default;
};

//---------------------------------------------
// 提供工厂实例的函数（由适配器实现）
//---------------------------------------------
std::unique_ptr<DPowerConfigManagerFactory> CreateJsonConfigFactory();

} // namespace Config
} // namespace DPower 
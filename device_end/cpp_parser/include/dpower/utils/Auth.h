#pragma once
// ================================================================
//  DPower::Utils::Auth 抽象接口
//  业务层仅依赖此接口，用于生成鉴权码。
// ================================================================

#include <string>
#include <memory>

namespace DPower {
namespace Utils {

//---------------------------------------------
// 前向声明 & 智能指针别名
//---------------------------------------------
class DPowerAuthGenerator;
class DPowerAuthFactory;

using AuthGeneratorPtr = std::unique_ptr<DPowerAuthGenerator>;
using AuthFactoryPtr = std::unique_ptr<DPowerAuthFactory>;

//---------------------------------------------
// 抽象接口定义
//---------------------------------------------

/**
 * @brief 鉴权码生成器接口
 */
class DPowerAuthGenerator {
public:
    virtual ~DPowerAuthGenerator() = default;

    /**
     * @brief 根据输入数据和密钥生成鉴权码
     * @param data 要进行认证的数据 (例如：设备ID)
     * @param key 服务器端存储的密钥
     * @return std::string Base64编码后的鉴权码
     */
    virtual std::string Generate(const std::string& data, const std::string& key) const = 0;
};

/**
 * @brief 鉴权码生成器工厂接口
 */
class DPowerAuthFactory {
public:
    virtual ~DPowerAuthFactory() = default;

    /**
     * @brief 创建一个鉴权码生成器实例
     * @return AuthGeneratorPtr 指向生成器实例的智能指针
     */
    virtual AuthGeneratorPtr Create() = 0;
};


//---------------------------------------------
// 抽象层工厂获取函数 (由各适配器实现)
//---------------------------------------------

/**
 * @brief 创建一个基于 OpenSSL 的鉴权码生成器工厂
 * @return AuthFactoryPtr 指向工厂实例的智能指针
 */
AuthFactoryPtr CreateOpenSSLAuthFactory();

} // namespace Utils
} // namespace DPower

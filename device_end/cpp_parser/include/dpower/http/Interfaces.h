#pragma once
// ================================================================
//  DPower::Http 抽象接口
//  业务层只依赖这些接口，底层实现可由 Boost.Asio / curl 替换
// ================================================================

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <map>

namespace DPower {
namespace Http {

//---------------------------------------------
// HTTP 响应结构
//---------------------------------------------
struct HttpResponse {
    int status_code = 0;
    std::string body;
    std::map<std::string, std::string> headers;
    std::string error_message;
    
    bool IsSuccess() const { return status_code >= 200 && status_code < 300; }
    bool IsUnauthorized() const { return status_code == 401; }
};

//---------------------------------------------
// HTTP 客户端抽象接口
//---------------------------------------------
class DPowerHttpClient {
public:
    virtual ~DPowerHttpClient() = default;
    
    /**
        * @brief 同步 POST JSON 请求
        * @param host 主机地址
        * @param port 端口
        * @param target 请求路径
        * @param json_body JSON 请求体
        * @param bearer_token 可选 Bearer Token
        * @param use_https 是否使用 HTTPS
        * @param verify_tls 是否校验证书（仅在 HTTPS 下生效）
        * @return HTTP 响应
     */
    virtual HttpResponse PostJson(const std::string& host,
                                  const std::string& port,
                                  const std::string& target,
                                  const std::string& json_body,
                                  const std::string& bearer_token = "",
                                  bool use_https = false,
                                  bool verify_tls = true) = 0;
};

using HttpClientPtr = std::shared_ptr<DPowerHttpClient>;

//---------------------------------------------
// HTTP 客户端工厂抽象接口
//---------------------------------------------
class DPowerHttpFactory {
public:
    virtual ~DPowerHttpFactory() = default;
    virtual HttpClientPtr CreateHttpClient() = 0;
};

using HttpFactoryPtr = std::unique_ptr<DPowerHttpFactory>;

//---------------------------------------------
// 工厂函数：返回默认实现（当前为 Boost 版本）
//---------------------------------------------
HttpFactoryPtr CreateBoostHttpFactory();

} // namespace Http
} // namespace DPower

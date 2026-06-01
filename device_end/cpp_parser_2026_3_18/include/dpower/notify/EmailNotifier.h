#pragma once

#include "dpower/http/Interfaces.h"
#include <string>
#include <memory>
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <chrono>

namespace DPower {
namespace Notify {

/**
 * @brief 异步邮件通知器
 * 
 * 后台线程发送 HTTP 请求，不阻塞主业务流程。
 * 支持 token 缓存和失败重试。
 */
class EmailNotifier {
public:
    /**
     * @brief 构造函数
     * @param http_client HTTP 客户端，如为空则使用默认 Boost 实现
     * @param api_host API 主机地址
     * @param api_port API 端口
     */
    explicit EmailNotifier(Http::HttpClientPtr http_client = nullptr,
                           const std::string& api_host = "127.0.0.1",
                           const std::string& api_port = "80");
    ~EmailNotifier();

    /**
     * @brief 投递故障邮件任务（非阻塞）
     * @param device_id 设备ID
     * @param fault_code 故障码
     * @param description 故障描述
     * @param event_level 事件级别
     */
    void EnqueueFaultEmail(const std::string& device_id,
                           const std::string& fault_code,
                           const std::string& description,
                           const std::string& event_level);

private:
    struct EmailTask {
        std::string subject;
        std::string content;
        std::string content_type; // plain or html
        std::string email_type;   // fault
    };

    void Worker();
    bool EnsureToken();
    bool RefreshToken();
    bool SendEmail(const EmailTask& task);

    // 内部状态
    std::mutex mutex_;
    std::condition_variable cv_;
    std::queue<EmailTask> queue_;
    bool stop_ = false;
    std::thread worker_;

    std::string token_;
    std::chrono::steady_clock::time_point token_expiry_ = std::chrono::steady_clock::now();

    Http::HttpClientPtr http_client_;
    std::string api_host_;
    std::string api_port_;
};

using EmailNotifierPtr = std::shared_ptr<EmailNotifier>;

/**
 * @brief 创建邮件通知器
 * @param http_client 可选的 HTTP 客户端
 * @param api_host API 主机地址
 * @param api_port API 端口
 * @return 邮件通知器共享指针
 */
EmailNotifierPtr CreateEmailNotifier(Http::HttpClientPtr http_client = nullptr,
                                     const std::string& api_host = "127.0.0.1",
                                     const std::string& api_port = "80");

} // namespace Notify
} // namespace DPower

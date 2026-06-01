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
 * 在后台线程发送 HTTP 请求，不阻塞业务主流程。
 * 支持失败重试。
 */
class EmailNotifier {
public:
    /**
     * @brief 构造函数
     * @param http_client HTTP 客户端，为空时使用默认 Boost 实现
    * @param api_host API 服务地址
    * @param api_port API 端口
     */
    explicit EmailNotifier(Http::HttpClientPtr http_client = nullptr,
                           const std::string& api_host = "127.0.0.1",
                           const std::string& api_port = "80",
                           bool use_https = false,
                           bool verify_tls = true);
    ~EmailNotifier();

    /**
     * @brief 投递故障邮件任务（非阻塞）
     * @param device_id 设备 ID
     * @param fault_code 故障码
     * @param description 故障描述
     * @param event_level 事件等级
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
    bool SendEmail(const EmailTask& task);

    // 内部状态
    std::mutex mutex_;
    std::condition_variable cv_;
    std::queue<EmailTask> queue_;
    bool stop_ = false;
    std::thread worker_;

    Http::HttpClientPtr http_client_;
    std::string api_host_;
    std::string api_port_;
    bool use_https_ = false;
    bool verify_tls_ = true;
};

using EmailNotifierPtr = std::shared_ptr<EmailNotifier>;

/**
 * @brief 创建邮件通知器
 * @param http_client 可选的 HTTP 客户端
 * @param api_host API 服务地址
 * @param api_port API 端口
 * @return 邮件通知器智能指针
 */
EmailNotifierPtr CreateEmailNotifier(Http::HttpClientPtr http_client = nullptr,
                                     const std::string& api_host = "127.0.0.1",
                                     const std::string& api_port = "80",
                                     bool use_https = false,
                                     bool verify_tls = true);

} // namespace Notify
} // namespace DPower

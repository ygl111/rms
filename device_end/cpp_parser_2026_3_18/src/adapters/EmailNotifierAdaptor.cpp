#include "dpower/notify/EmailNotifier.h"
#include "dpower/http/Interfaces.h"
#include "json.hpp"
#include <sstream>
#include <iostream>

using json = nlohmann::json;

namespace DPower {
namespace Notify {

namespace {
constexpr const char* kLoginPath = "/api/auth/login";
constexpr const char* kSendPath = "/api/send-email";
constexpr int kMaxAttempts = 3;
} // anonymous namespace

EmailNotifier::EmailNotifier(Http::HttpClientPtr http_client,
                             const std::string& api_host,
                             const std::string& api_port)
    : http_client_(std::move(http_client)),
      api_host_(api_host),
      api_port_(api_port) {
    if (!http_client_) {
        auto factory = Http::CreateBoostHttpFactory();
        http_client_ = factory->CreateHttpClient();
    }
    worker_ = std::thread([this]() { Worker(); });
}

EmailNotifier::~EmailNotifier() {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        stop_ = true;
    }
    cv_.notify_all();
    if (worker_.joinable()) {
        worker_.join();
    }
}

void EmailNotifier::EnqueueFaultEmail(const std::string& device_id,
                                      const std::string& fault_code,
                                      const std::string& description,
                                      const std::string& event_level) {
    EmailTask task;
    task.email_type = "fault";
    // 使用 ASCII 安全的格式避免编码问题
    task.subject = "Device Fault: " + device_id + " (" + fault_code + ")";
    std::ostringstream content;
    content << "Device: " << device_id << "\n"
            << "Fault Code: " << fault_code << "\n";
    if (!event_level.empty()) {
        content << "Level: " << event_level << "\n";
    }
    if (!description.empty()) {
        content << "Description: " << description << "\n";
    }
    task.content = content.str();
    task.content_type = "plain";

    {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(std::move(task));
    }
    cv_.notify_one();
    std::cout << "[EmailNotifier] Enqueued fault email for device: " << device_id << std::endl;
}

void EmailNotifier::Worker() {
    while (true) {
        EmailTask task;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [this]() { return stop_ || !queue_.empty(); });
            if (stop_ && queue_.empty()) {
                return;
            }
            task = std::move(queue_.front());
            queue_.pop();
        }

        int attempts = 0;
        while (attempts < kMaxAttempts) {
            if (!EnsureToken()) {
                ++attempts;
                std::this_thread::sleep_for(std::chrono::milliseconds(200 * attempts));
                continue;
            }
            if (SendEmail(task)) {
                std::cout << "[EmailNotifier] Email sent successfully: " << task.subject << std::endl;
                break;
            }
            // token 可能失效，尝试刷新
            token_.clear();
            ++attempts;
            std::this_thread::sleep_for(std::chrono::milliseconds(200 * attempts));
        }
        if (attempts >= kMaxAttempts) {
            std::cerr << "[EmailNotifier] Failed to send email after " << kMaxAttempts 
                      << " attempts: " << task.subject << std::endl;
        }
    }
}

bool EmailNotifier::EnsureToken() {
    auto now = std::chrono::steady_clock::now();
    if (!token_.empty() && now < token_expiry_) {
        return true;
    }
    return RefreshToken();
}

bool EmailNotifier::RefreshToken() {
    json payload = {
        {"account", "admin"},
        {"password", "1234"}
    };
    auto resp = http_client_->PostJson(api_host_, api_port_, kLoginPath, payload.dump());
    
    // 调试日志：打印响应状态和内容
    std::cout << "[EmailNotifier] Login response status=" << resp.status_code 
              << ", body_length=" << resp.body.size() << std::endl;
    if (!resp.body.empty()) {
        // 打印前200个字符用于调试
        std::string preview = resp.body.substr(0, std::min(resp.body.size(), size_t(200)));
        std::cout << "[EmailNotifier] Response preview: " << preview << std::endl;
    }
    
    if (resp.status_code != 200) {
        std::cerr << "[EmailNotifier] Login failed, status=" << resp.status_code 
                  << " error=" << resp.error_message << std::endl;
        return false;
    }
    
    // 尝试跳过可能的 HTTP headers（查找第一个 '{' 或 '['）
    std::string json_body = resp.body;
    size_t json_start = json_body.find_first_of("{[");
    if (json_start != std::string::npos && json_start > 0) {
        json_body = json_body.substr(json_start);
    }
    
    auto j = json::parse(json_body, nullptr, false);
    if (j.is_discarded()) {
        std::cerr << "[EmailNotifier] Login response parse failed, body: " 
                  << json_body.substr(0, 100) << std::endl;
        return false;
    }
    // 支持多种响应格式
    if (j.contains("access_token") && j["access_token"].is_string()) {
        token_ = j["access_token"].get<std::string>();
    } else if (j.contains("token") && j["token"].is_string()) {
        token_ = j["token"].get<std::string>();
    } else if (j.contains("data") && j["data"].is_object()) {
        auto& data = j["data"];
        if (data.contains("access_token") && data["access_token"].is_string()) {
            token_ = data["access_token"].get<std::string>();
        } else if (data.contains("token") && data["token"].is_string()) {
            token_ = data["token"].get<std::string>();
        }
    }
    
    if (token_.empty()) {
        std::cerr << "[EmailNotifier] Login response missing token" << std::endl;
        return false;
    }
    // 设定 token 10 分钟有效（若服务端未返回过期时间）
    token_expiry_ = std::chrono::steady_clock::now() + std::chrono::minutes(10);
    std::cout << "[EmailNotifier] Token refreshed successfully" << std::endl;
    return true;
}

bool EmailNotifier::SendEmail(const EmailTask& task) {
    try {
        json payload = {
            {"email_type", task.email_type},
            {"subject", task.subject},
            {"content", task.content},
            {"content_type", task.content_type}
        };
        // 使用 error_handler_t::replace 来安全处理可能的编码问题
        std::string body = payload.dump(-1, ' ', false, json::error_handler_t::replace);
        auto resp = http_client_->PostJson(api_host_, api_port_, kSendPath, body, token_);
        if (resp.IsUnauthorized()) {
            // token 失效
            return false;
        }
        if (!resp.IsSuccess()) {
            std::cerr << "[EmailNotifier] Send email failed, status=" << resp.status_code 
                      << " error=" << resp.error_message << std::endl;
            return false;
        }
        std::cout << "[EmailNotifier] Email sent successfully: " << task.subject << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "[EmailNotifier] SendEmail exception: " << e.what() << std::endl;
        return false;
    }
}

EmailNotifierPtr CreateEmailNotifier(Http::HttpClientPtr http_client,
                                     const std::string& api_host,
                                     const std::string& api_port) {
    return std::make_shared<EmailNotifier>(std::move(http_client), api_host, api_port);
}

} // namespace Notify
} // namespace DPower

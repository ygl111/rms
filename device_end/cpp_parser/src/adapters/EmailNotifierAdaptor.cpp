#include "dpower/notify/EmailNotifier.h"
#include "dpower/http/Interfaces.h"
#include "json.hpp"
#include <sstream>
#include <iostream>

using json = nlohmann::json;

namespace DPower {
namespace Notify {

namespace {
constexpr const char* kSendPath = "/api/send-email";
constexpr int kMaxAttempts = 3;
} // anonymous namespace

EmailNotifier::EmailNotifier(Http::HttpClientPtr http_client,
                             const std::string& api_host,
                     const std::string& api_port,
                     bool use_https,
                     bool verify_tls)
    : http_client_(std::move(http_client)),
      api_host_(api_host),
    api_port_(api_port),
    use_https_(use_https),
    verify_tls_(verify_tls) {
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
    // 使用 ASCII 安全的主题格式，避免编码问题。
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
        size_t pending_after_pop = 0;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [this]() { return stop_ || !queue_.empty(); });
            if (stop_ && queue_.empty()) {
                return;
            }
            task = std::move(queue_.front());
            queue_.pop();
            pending_after_pop = queue_.size();
        }

        std::cout << "[EmailNotifier] Dequeued email task: subject='" << task.subject
                  << "', pending_queue=" << pending_after_pop << std::endl;

        int attempts = 0;
        while (attempts < kMaxAttempts) {
            std::cout << "[EmailNotifier] Sending attempt " << (attempts + 1)
                      << "/" << kMaxAttempts << " for subject='" << task.subject << "'" << std::endl;
            if (SendEmail(task)) {
                std::cout << "[EmailNotifier] Email sent successfully: " << task.subject << std::endl;
                break;
            }
            ++attempts;
            std::cerr << "[EmailNotifier] Send attempt failed for subject='" << task.subject
                      << "', attempt=" << attempts << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(200 * attempts));
        }
        if (attempts >= kMaxAttempts) {
            std::cerr << "[EmailNotifier] Failed to send email after " << kMaxAttempts 
                      << " attempts: " << task.subject << std::endl;
        }
    }
}

bool EmailNotifier::SendEmail(const EmailTask& task) {
    try {
        json payload = {
            {"email_type", task.email_type},
            {"subject", task.subject},
            {"content", task.content},
            {"content_type", task.content_type}
        };
        // 使用 replace 处理器，安全序列化可能包含无效 UTF-8 的文本。
        std::string body = payload.dump(-1, ' ', false, json::error_handler_t::replace);
        auto resp = http_client_->PostJson(api_host_, api_port_, kSendPath, body, "", use_https_, verify_tls_);
        if (!resp.IsSuccess()) {
            std::string preview = resp.body.substr(0, std::min<size_t>(resp.body.size(), 300));
            std::cerr << "[EmailNotifier] Send email failed, status=" << resp.status_code 
                      << " error=" << resp.error_message
                      << " response_body_preview=" << preview << std::endl;
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
                                     const std::string& api_port,
                                     bool use_https,
                                     bool verify_tls) {
    return std::make_shared<EmailNotifier>(std::move(http_client), api_host, api_port, use_https, verify_tls);
}

} // namespace Notify
} // namespace DPower

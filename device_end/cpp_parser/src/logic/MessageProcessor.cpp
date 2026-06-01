#include "logic/MessageProcessor.h"
#include "logic/utils/MessageUtils.h"
#include "logic/services/DeviceServiceImpl.h"
#include "logic/services/BanknoteServiceImpl.h"
#include "logic/services/FaultServiceImpl.h"
#include "logic/services/UpgradeServiceImpl.h"
#include "dpower/notify/EmailNotifier.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <thread>
#include <algorithm>
#include <functional>
#include <json.hpp>
#include <numeric>
#include "logic/utils/Logger.h"

// ProcessingStats实现
void InternalProcessingStats::UpdateStats(uint16_t msg_id, long long processing_time_ms) {
    std::lock_guard<std::mutex> lock(stats_mutex);
    
    messages_processed++;
    total_processing_time_ms += processing_time_ms;
    
    long long processed = messages_processed.load();
    if (processed > 0) {
        avg_processing_time_ms = total_processing_time_ms.load() / processed;
    }
    
    message_type_counts[msg_id]++;
    last_update_time = std::chrono::system_clock::now();
}

std::map<std::string, long long> ProcessingStats::GetStatsMap() const {
    std::map<std::string, long long> stats;
    stats["messages_processed"] = messages_processed;
    stats["messages_failed"] = messages_failed;
    stats["responses_generated"] = responses_generated;
    stats["avg_processing_time_ms"] = avg_processing_time_ms;
    stats["total_processing_time_ms"] = total_processing_time_ms;
    
    return stats;
}

std::map<std::string, long long> InternalProcessingStats::GetStatsMap() const {
    std::lock_guard<std::mutex> lock(stats_mutex);
    
    std::map<std::string, long long> stats;
    stats["messages_processed"] = messages_processed.load();
    stats["messages_failed"] = messages_failed.load();
    stats["responses_generated"] = responses_generated.load();
    stats["avg_processing_time_ms"] = avg_processing_time_ms.load();
    stats["total_processing_time_ms"] = total_processing_time_ms.load();
    
    return stats;
}

void InternalProcessingStats::Reset() {
    std::lock_guard<std::mutex> lock(stats_mutex);
    
    messages_processed = 0;
    messages_failed = 0;
    responses_generated = 0;
    total_processing_time_ms = 0;
    avg_processing_time_ms = 0;
    message_type_counts.clear();
    start_time = std::chrono::system_clock::now();
    last_update_time = start_time;
}

// MessageProcessor实现

// 构造函数，接收数据库和缓存客户端
MessageProcessor::MessageProcessor(
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
        std::shared_ptr<DPower::MQ::DPowerMqClient> rabbitmq_client,
    const ParserConfig::FtpConfig& ftp_config)
    : db_client_(std::move(db_client)),
      cache_client_(std::move(cache_client)),
      mq_client_(std::move(mq_client)),
            rabbitmq_client_(std::move(rabbitmq_client)),
      ftp_config_(ftp_config)
{
    // 在构造时就进行检查，如果传入的是空指针，程序将无法创建此对象，直接抛出异常
    if (!db_client_) {
        throw std::invalid_argument("Database client provided to MessageProcessor cannot be null.");
    }
    if (!cache_client_) {
        throw std::invalid_argument("Cache client provided to MessageProcessor cannot be null.");
    }
    if (!mq_client_) { // <--- 增加对消息队列客户端的检查
        throw std::invalid_argument("Message queue client provided to MessageProcessor cannot be null.");
    }

    // 初始化内部状态
    stats_.start_time = std::chrono::system_clock::now();
    stats_.last_update_time = stats_.start_time;
    last_health_check_ = std::chrono::system_clock::now();
    last_message_time_ = std::chrono::system_clock::now();
}

MessageProcessor::~MessageProcessor() {
    Stop();
}

bool MessageProcessor::Initialize(const ParserConfig& config) {
    config_ = config;
    
    // 初始化多协议管理器
    protocol_manager_ = std::make_shared<MultiProtocolManager>();
    if (!protocol_manager_->LoadProtocolRegistry("config/protocol_registry.json")) {
        Log("ERROR", "Failed to load protocol registry");
        return false;
    }
    
    // 初始化通用解析器
    universal_parser_ = std::make_shared<UniversalParser>();
    // 启用/禁用schema推导
    universal_parser_->EnableSchemaResolver(config_.protocol.enable_schema_resolver);
    // 新增：打印schema解析器开关状态
    Log("INFO", std::string("Schema resolver is ") + (config_.protocol.enable_schema_resolver ? "ENABLED" : "DISABLED"));
    
    // 自动加载所有协议的 schema（若协议配置看起来像DP schema）
    try {
        auto supported = protocol_manager_->GetSupportedProtocols();
        // 新增：记录加载结果
        std::vector<std::string> loaded_schemas;
        std::vector<std::string> skipped_schemas;
        for (const auto& pid : supported) {
            auto schema = protocol_manager_->GetProtocolConfig(pid);
            if (!schema.is_null() && schema.contains("messages") && schema.contains("header")) {
                (void)universal_parser_->LoadProtocolSchemaJson(pid, schema);
                loaded_schemas.push_back(pid);
            } else {
                skipped_schemas.push_back(pid);
            }
        }
        // 新增：打印协议与加载摘要
        if (!supported.empty()) {
            std::stringstream ss_all, ss_loaded, ss_skipped;
            ss_all << "Protocols in registry: ";
            for (size_t i = 0; i < supported.size(); ++i) { if (i) ss_all << ", "; ss_all << supported[i]; }
            Log("INFO", ss_all.str());
            ss_loaded << "Schemas loaded (" << loaded_schemas.size() << "): ";
            for (size_t i = 0; i < loaded_schemas.size(); ++i) { if (i) ss_loaded << ", "; ss_loaded << loaded_schemas[i]; }
            Log("INFO", ss_loaded.str());
            if (!skipped_schemas.empty()) {
                ss_skipped << "Schemas skipped (no DP-style schema) (" << skipped_schemas.size() << "): ";
                for (size_t i = 0; i < skipped_schemas.size(); ++i) { if (i) ss_skipped << ", "; ss_skipped << skipped_schemas[i]; }
                Log("DEBUG", ss_skipped.str());
            }
        }
    } catch (const std::exception& e) {
        Log("WARN", std::string("Load all schemas failed: ") + e.what());
    }

    if (!universal_parser_->LoadParsingRules("config/universal_parsing_rules.json")) {
        Log("ERROR", "Failed to load universal parsing rules");
        return false;
    }
    if (!universal_parser_->LoadProtocolStrategies("config/protocol_parsing_strategies.json")) {
        Log("ERROR", "Failed to load protocol parsing strategies");
        return false;
    }
    
    // 初始化响应生成器
    response_generator_ = std::make_shared<ResponseGenerator>();
    if (!response_generator_->Initialize(universal_parser_, protocol_manager_)) {
        Log("ERROR", "Failed to initialize response generator");
        return false;
    }
    
    // 初始化服务层
    DPower::Notify::EmailNotifierPtr email_notifier = nullptr;
    if (config_.notification.enable_email_notification) {
        // 创建邮件通知器（异步后台发送，不阻塞主流程）
        email_notifier = DPower::Notify::CreateEmailNotifier(
            nullptr,
            config_.notification.email_api_host,
            config_.notification.email_api_port,
            config_.notification.email_api_https,
            config_.notification.email_api_verify_tls);
        Log("INFO", "Email notification is enabled");
    } else {
        Log("INFO", "Email notification is disabled by config");
    }
    
    device_service_ = std::make_shared<DeviceServiceImpl>(
        db_client_,
        cache_client_,
        mq_client_,
        response_generator_,
        ftp_config_,
        config_.auth,
        config_.monitor.offline_detection_poll_interval_seconds,
        config_.monitor.offline_detection_timeout_seconds);
    banknote_service_ = std::make_shared<BanknoteServiceImpl>(
        db_client_, cache_client_, mq_client_, rabbitmq_client_, config_.rabbitmq.worktime_queue);
    fault_service_ = std::make_shared<FaultServiceImpl>(db_client_, cache_client_, mq_client_, email_notifier);
    upgrade_service_ = std::make_shared<UpgradeServiceImpl>(db_client_, cache_client_, mq_client_);
    
    // 初始化消息处理器工厂
    handler_factory_ = std::make_unique<MessageHandlerFactory>(
        device_service_, banknote_service_, fault_service_, upgrade_service_, response_generator_);
    
    Log("INFO", "MessageProcessor initialized successfully");

    return true;
}

bool MessageProcessor::Start() {
    if (running_) {
        Log("WARN", "MessageProcessor already running");
        return true;
    }
    
    should_stop_ = false;
    running_ = true;
    
    // 启动工作线程
    for (int i = 0; i < config_.thread.worker_threads; ++i) {
        worker_threads_.emplace_back(&MessageProcessor::WorkerThread, this, i);
    }
    
    // 启动消息读取线程
    worker_threads_.emplace_back(&MessageProcessor::ReaderThread, this);
    
    // 初始化在线设备(从数据库加载)
    InitializeOnlineDevices();
    
    // 启动离线检测线程
    StartOfflineDetection();
    
    Log("INFO", "MessageProcessor started with " + std::to_string(config_.thread.worker_threads) + " worker threads");
    return true;
}

void MessageProcessor::Stop() {
    if (!running_) {
        return;
    }
    
    Log("INFO", "Stopping MessageProcessor...");
    
    should_stop_ = true;
    queue_cv_.notify_all();
    
    // 停止离线检测线程
    StopOfflineDetection();
    
    // 等待所有线程结束
    for (auto& thread : worker_threads_) {
        if (thread.joinable()) {
            thread.join();
        }
    }
    
    worker_threads_.clear();
    running_ = false;
    
    Log("INFO", "MessageProcessor stopped");
}

bool MessageProcessor::IsRunning() const {
    return running_;
}

bool MessageProcessor::ProcessMessage(const DPower::Redis::DPowerRedisMessage& message) {
    auto start_time = std::chrono::system_clock::now();
    const int max_attempts = std::max(1, config_.redis.process_max_retries);
    const int retry_backoff_ms = std::max(0, config_.redis.retry_backoff_ms);

    auto ack_message = [&]() {
        if (message.id.empty()) {
            return;
        }
        auto ack_result = mq_client_->AckMessage(
            config_.redis.request_stream_key,
            config_.redis.consumer_group,
            message.id);
        if (!ack_result.success) {
            Log("ERROR", "Failed to ACK message id=" + message.id + ", err=" + ack_result.error_message);
        }
    };

    auto push_to_dlq = [&](const std::string& final_reason, int attempts) {
        nlohmann::json dlq_payload;
        dlq_payload["original_id"] = message.id;
        dlq_payload["stream_key"] = message.stream_key;
        dlq_payload["source_ip"] = message.source_ip;
        dlq_payload["raw_data_base64"] = message.raw_data_base64;
        dlq_payload["attempts"] = attempts;
        dlq_payload["final_reason"] = final_reason;
        dlq_payload["dropped_at_ms"] = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        nlohmann::json additional = nlohmann::json::object();
        for (const auto& kv : message.additional_fields) {
            additional[kv.first] = kv.second;
        }
        dlq_payload["additional_fields"] = additional;

        auto dlq_result = mq_client_->ExecuteCommand(
            "LPUSH " + config_.redis.dead_letter_queue_key + " " + dlq_payload.dump());
        if (dlq_result.success) {
            Log("WARN", "Message moved to DLQ id=" + message.id + ", attempts=" +
                std::to_string(attempts) + ", reason=" + final_reason);
        } else {
            Log("ERROR", "Failed to move message to DLQ id=" + message.id + ", err=" + dlq_result.error_message);
        }
    };

    std::string last_failure_reason = "unknown";

    for (int attempt = 1; attempt <= max_attempts; ++attempt) {
        try {
            // 从消息中提取协议信息（支持从 additional_fields 归一化获取）
            std::string protocol_id = "dp_protocol_v1"; // 默认协议
            std::string protocol_source = "default";
            // 来自 tcp_gateway 的协议信息提示
            std::string protocol_hint_id;
            std::string protocol_hint_name;
            std::string protocol_hint_version;
            if (message.additional_fields.find("protocol_id") != message.additional_fields.end()) {
                protocol_hint_id = message.additional_fields.at("protocol_id");
            }
            if (message.additional_fields.find("protocol_name") != message.additional_fields.end()) {
                protocol_hint_name = message.additional_fields.at("protocol_name");
            }
            if (message.additional_fields.find("protocol_version") != message.additional_fields.end()) {
                protocol_hint_version = message.additional_fields.at("protocol_version");
            }
            if (!protocol_hint_id.empty() || !protocol_hint_name.empty() || !protocol_hint_version.empty()) {
                Log("DEBUG", std::string("Inbound protocol hints: id=") + (protocol_hint_id.empty()?"<none>":protocol_hint_id)
                    + ", name=" + (protocol_hint_name.empty()?"<none>":protocol_hint_name)
                    + ", version=" + (protocol_hint_version.empty()?"<none>":protocol_hint_version));
            }

            auto has_strategy = [&](const std::string& pid)->bool {
                return universal_parser_ && !pid.empty() && universal_parser_->GetProtocolStrategy(pid).has_value();
            };
            auto to_lower = [](std::string s){ std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c){ return static_cast<char>(std::tolower(c)); }); return s; };

            // 优先使用 protocol_id，其次 protocol_name；尝试归一化（去除版本后缀/大小写）
            bool hint_present = false;
            std::string resolved;
            std::string resolve_method;
            if (!protocol_hint_id.empty()) {
                hint_present = true;
                if (has_strategy(protocol_hint_id)) { resolved = protocol_hint_id; resolve_method = "protocol_id(exact)"; }
                if (resolved.empty()) {
                    std::string tmp = protocol_hint_id;
                    // 逐步去掉末尾的分隔段（支持 '_' 和 '-'）
                    for (char sep : std::string("_-")) {
                        tmp = protocol_hint_id;
                        while (true) {
                            auto pos = tmp.rfind(sep);
                            if (pos == std::string::npos) break;
                            tmp = tmp.substr(0, pos);
                            if (has_strategy(tmp)) { resolved = tmp; resolve_method = std::string("protocol_id(normalized)") + sep; break; }
                        }
                        if (!resolved.empty()) break;
                    }
                }
                if (resolved.empty()) {
                    auto lower = to_lower(protocol_hint_id);
                    if (has_strategy(lower)) { resolved = lower; resolve_method = "protocol_id(lowercase)"; }
                }
            }
            if (resolved.empty() && !protocol_hint_name.empty()) {
                hint_present = true;
                if (has_strategy(protocol_hint_name)) { resolved = protocol_hint_name; resolve_method = "protocol_name(exact)"; }
                if (resolved.empty()) {
                    auto lower = to_lower(protocol_hint_name);
                    if (has_strategy(lower)) { resolved = lower; resolve_method = "protocol_name(lowercase)"; }
                }
            }

            if (!resolved.empty()) {
                protocol_id = resolved;
                protocol_source = "message.additional_fields(" + resolve_method + ")";
            } else if (hint_present) {
                // 有提示但无法识别，标注回退
                protocol_source = "default(fallback)";
            }

            // 打印本次消息采用的协议及来源
            Log("DEBUG", "Protocol selected: " + protocol_id + " (source: " + protocol_source + ")");

            // 新增：签名探测所有协议候选（仅日志，不改变实际解析）
            try {
                std::vector<uint8_t> raw_data = universal_parser_->DecodeBase64(message.raw_data_base64);
                if (!raw_data.empty() && protocol_manager_) {
                    std::vector<std::string> candidates;
                    auto supported = protocol_manager_->GetSupportedProtocols();
                    for (const auto& pid : supported) {
                        auto stratOpt = universal_parser_->GetProtocolStrategy(pid);
                        if (!stratOpt.has_value()) continue;
                        const auto& strat = stratOpt.value();

                        bool header_ok = true;
                        if (!strat.header_signature.empty()) {
                            if (strat.header_signature_offset + (int)strat.header_signature.size() > (int)raw_data.size()) {
                                header_ok = false;
                            } else {
                                for (size_t i = 0; i < strat.header_signature.size(); ++i) {
                                    if (raw_data[strat.header_signature_offset + i] != strat.header_signature[i]) { header_ok = false; break; }
                                }
                            }
                        }

                        bool tail_ok = true;
                        if (!strat.tail_signature.empty()) {
                            if (strat.tail_signature.size() > raw_data.size()) {
                                tail_ok = false;
                            } else {
                                size_t tail_pos = raw_data.size() - strat.tail_signature.size();
                                for (size_t i = 0; i < strat.tail_signature.size(); ++i) {
                                    if (raw_data[tail_pos + i] != strat.tail_signature[i]) { tail_ok = false; break; }
                                }
                            }
                        }

                        if (header_ok && tail_ok) {
                            candidates.push_back(pid);
                        }
                    }
                    if (!candidates.empty()) {
                        std::stringstream ss; ss << "Protocol candidates by signature: ";
                        for (size_t i = 0; i < candidates.size(); ++i) { if (i) ss << ", "; ss << candidates[i]; }
                        Log("DEBUG", ss.str());
                    } else {
                        Log("DEBUG", "Protocol candidates by signature: <none>");
                    }
                }
            } catch (...) { /* 调试探测忽略异常 */ }

            // 使用通用解析器解析消息
            UniversalParsedMessage parsed_msg = universal_parser_->ParseMessage(protocol_id, message.raw_data_base64, message.source_ip);

            if (!parsed_msg.is_valid) {
                last_failure_reason = "parse_failed:" + parsed_msg.error_message;
                Log("ERROR", "Failed to parse message (attempt " + std::to_string(attempt) + "/" +
                    std::to_string(max_attempts) + "): " + parsed_msg.error_message);
                if (attempt < max_attempts && retry_backoff_ms > 0) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(retry_backoff_ms));
                }
                continue;
            }
            // 新增：打印解析成功后实际使用的协议与消息ID
            Log("DEBUG", "Parsed with protocol: " + parsed_msg.protocol_id + ", msg_id: " + std::to_string(parsed_msg.msg_id));

            // 验证消息
            if (!ValidateMessage(parsed_msg)) {
                last_failure_reason = "validation_failed:msg_id=" + std::to_string(parsed_msg.msg_id);
                Log("ERROR", "Message validation failed for msg_id: " + std::to_string(parsed_msg.msg_id) +
                    " (attempt " + std::to_string(attempt) + "/" + std::to_string(max_attempts) + ")");
                if (attempt < max_attempts && retry_backoff_ms > 0) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(retry_backoff_ms));
                }
                continue;
            }

            // 处理消息
            std::vector<uint8_t> response = ProcessParsedMessage(parsed_msg);

            // 发送响应
            if (!response.empty() && ShouldRespond(parsed_msg.msg_id)) {
                if (SendResponse(response, message.source_ip)) {
                    stats_.responses_generated++;
                }
            }

            // 调用回调函数
            if (message_callback_) {
                message_callback_(parsed_msg, response);
            }

            // 确认消息处理
            ack_message();

            // 更新统计信息
            long long processing_time = CalculateProcessingTime(start_time);
            stats_.UpdateStats(parsed_msg.msg_id, processing_time);

            if (config_.log.enable_performance_log) {
                LogPerformance(parsed_msg.msg_id, processing_time);
            }

            UpdateLastMessageTime();

            Log("DEBUG", "Successfully processed message: " + GetMessageTypeName(parsed_msg.msg_id) + " (ID: " + std::to_string(parsed_msg.msg_id) + ")");

            return true;

        } catch (const std::exception& e) {
            last_failure_reason = std::string("exception:") + e.what();
            HandleError("Exception in ProcessMessage attempt " + std::to_string(attempt) + "/" +
                        std::to_string(max_attempts) + ": " + std::string(e.what()));
            if (attempt < max_attempts && retry_backoff_ms > 0) {
                std::this_thread::sleep_for(std::chrono::milliseconds(retry_backoff_ms));
            }
        }
    }

    stats_.messages_failed++;
    push_to_dlq(last_failure_reason, max_attempts);
    ack_message();
    return false;
}

ProcessingStats MessageProcessor::GetStats() const {
    ProcessingStats result;
    std::lock_guard<std::mutex> lock(stats_.stats_mutex);
    result.messages_processed = stats_.messages_processed.load();
    result.messages_failed = stats_.messages_failed.load();
    result.responses_generated = stats_.responses_generated.load();
    result.total_processing_time_ms = stats_.total_processing_time_ms.load();
    result.avg_processing_time_ms = stats_.avg_processing_time_ms.load();
    result.start_time = stats_.start_time;
    result.last_update_time = stats_.last_update_time;
    result.message_type_counts = stats_.message_type_counts;
    return result;
}

void MessageProcessor::ResetStats() {
    stats_.Reset();
}

void MessageProcessor::SetMessageCallback(std::function<void(const UniversalParsedMessage&, const std::vector<uint8_t>&)> callback) {
    message_callback_ = callback;
}

void MessageProcessor::SetErrorCallback(std::function<void(const std::string&)> callback) {
    error_callback_ = callback;
}

std::map<std::string, std::string> MessageProcessor::GetHealthStatus() const {
    std::map<std::string, std::string> status;
    
    status["running"] = running_ ? "true" : "false";
    status["redis_connected"] = mq_client_&& mq_client_->IsConnected() ? "true" : "false";
    status["queue_health"] = CheckQueueHealth() ? "healthy" : "unhealthy";
    status["last_message_time"] = FormatTime(last_message_time_);
    status["last_health_check"] = FormatTime(last_health_check_);
    
    auto stats = stats_.GetStatsMap();
    status["messages_processed"] = std::to_string(stats["messages_processed"]);
    status["messages_failed"] = std::to_string(stats["messages_failed"]);
    status["avg_processing_time_ms"] = std::to_string(stats["avg_processing_time_ms"]);
    
    return status;
}

bool MessageProcessor::HealthCheck() {
    last_health_check_ = std::chrono::system_clock::now();
    
    if (!running_) {
        return false;
    }
    
    if (!CheckRedisHealth()) {
        Log("ERROR", "Redis health check failed");
        return false;
    }
    
    if (!CheckQueueHealth()) {
        Log("ERROR", "Queue health check failed");
        return false;
    }
    
    return true;
}

ParserConfig MessageProcessor::GetConfig() const {
    return config_;
}

bool MessageProcessor::UpdateConfig(const ParserConfig& config) {
    // 对于运行时配置更新，需要谨慎处理
    // 这里只更新部分可以动态更新的配置
    config_.log = config.log;
    config_.monitor = config.monitor;
    
    // 如果尚未启动，可以更新线程配置
    if (!running_) {
        config_.thread = config.thread;
        Log("INFO", "Thread configuration updated before start");
    } else {
        Log("WARN", "Cannot update thread configuration while running");
    }
    
    // 更新响应生成器的参数
    if (response_generator_) {
        response_generator_->SetHeartbeatParams(180, 1); // 可以从配置中读取
    }
    
    return true;
}

// 私有方法实现
void MessageProcessor::WorkerThread(int thread_id) {
    Log("INFO", "Worker thread " + std::to_string(thread_id) + " started");
    
    while (!should_stop_) {
        DPower::Redis::DPowerRedisMessage message;
        
        // 从队列中获取消息
        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            queue_cv_.wait(lock, [this] { return !message_queue_.empty() || should_stop_; });
            
            if (should_stop_ && message_queue_.empty()) {
                break;
            }
            
            if (!message_queue_.empty()) {
                message = message_queue_.front();
                message_queue_.pop();
            } else {
                continue;
            }
        }
        
        // 处理消息
        ProcessMessage(message);
    }
    
    Log("INFO", "Worker thread " + std::to_string(thread_id) + " stopped");
}

void MessageProcessor::ReaderThread() {
    Log("INFO", "Reader thread started");
    constexpr int kPelMinIdleMs = 60000;
    
    while (!should_stop_) {
        try {
            // 从Redis读取消息
            auto messages = mq_client_->ReadFromStream(
                config_.redis.request_stream_key,
                config_.redis.consumer_group,
                config_.redis.consumer_name,
                config_.thread.batch_size,
                config_.redis.block_timeout
            );

            // 没有新消息时，尝试回收 PEL 中超时未确认消息（例如旧消费者宕机导致的遗留消息）。
            if (messages.empty()) {
                auto reclaimed = mq_client_->AutoClaimPendingFromStream(
                    config_.redis.request_stream_key,
                    config_.redis.consumer_group,
                    config_.redis.consumer_name,
                    kPelMinIdleMs,
                    config_.thread.batch_size,
                    pel_claim_start_id_);

                if (!reclaimed.empty()) {
                    Log("INFO", "Reclaimed " + std::to_string(reclaimed.size()) +
                                " pending messages from PEL");
                    messages = std::move(reclaimed);
                }
            }
            
            if (!messages.empty()) {
                // 将消息加入队列
                {
                    std::lock_guard<std::mutex> lock(queue_mutex_);
                    for (const auto& msg : messages) {
                        if (message_queue_.size() < static_cast<size_t>(config_.thread.queue_size)) {
                            message_queue_.push(msg);
                        } else {
                            Log("WARN", "Message queue full, dropping message");
                            stats_.messages_failed++;
                        }
                    }
                }
                queue_cv_.notify_all();
            } else {
                // 没有消息时短暂休息，避免过度消耗CPU
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            
        } catch (const std::exception& e) {
            HandleError("Exception in ReaderThread: " + std::string(e.what()));
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
    
    Log("INFO", "Reader thread stopped");
}

void MessageProcessor::StatsThread() {
    Log("INFO", "Stats thread started");
    
    while (!should_stop_) {
        std::this_thread::sleep_for(std::chrono::seconds(config_.monitor.stats_interval));
        
        if (should_stop_) break;
        
        auto stats = stats_.GetStatsMap();
        std::stringstream ss;
        ss << "Processing stats - ";
        ss << "Processed: " << stats["messages_processed"] << ", ";
        ss << "Failed: " << stats["messages_failed"] << ", ";
        ss << "Responses: " << stats["responses_generated"] << ", ";
        ss << "Avg time: " << stats["avg_processing_time_ms"] << "ms";
        
        Log("INFO", ss.str());
    }
    
    Log("INFO", "Stats thread stopped");
}

std::vector<uint8_t> MessageProcessor::ProcessParsedMessage(const UniversalParsedMessage& parsed_msg) {
    Log("DEBUG", "Entering ProcessParsedMessage with msg_id: " + std::to_string(parsed_msg.msg_id));
    
    // 使用Handler模式处理通用解析后的消息
    auto handler = handler_factory_->GetHandler(parsed_msg.msg_id);
    if (handler) {
        Log("DEBUG", "Found handler: " + handler->GetHandlerName());

        return handler->Handle(parsed_msg);
    }
    
    // 对于不支持的消息类型，返回通用错误响应
    Log("WARN", "Unsupported message type: " + std::to_string(parsed_msg.msg_id));
    
    return response_generator_->CreateGenericResponse(parsed_msg, 0x01, "Unsupported message type");
}

// 设备状态管理由DeviceService处理

void MessageProcessor::StartOfflineDetection() {
    // 调用DeviceService的离线检测方法
    if (device_service_) {
        device_service_->StartOfflineDetection();
    } else {
        Log("ERROR", "DeviceService not available, cannot start offline detection");
    }
}

void MessageProcessor::InitializeOnlineDevices() {
    // 调用DeviceService的初始化在线设备方法
    if (device_service_) {
        device_service_->InitializeOnlineDevices();
    } else {
        Log("ERROR", "DeviceService not available, cannot initialize online devices");
    }
}

void MessageProcessor::StopOfflineDetection() {
    // 调用DeviceService的停止离线检测方法
    if (device_service_) {
        device_service_->StopOfflineDetection();
    }
}




bool MessageProcessor::SendResponse(const std::vector<uint8_t>& response_data, const std::string& source_ip) {
    if (response_data.empty()) {
        return false;
    }
    
    try {
        // 创建响应对象
        DPower::Redis::DPowerRedisResponse response;
        response.client_id = source_ip;
        // 使用默认协议解析器进行Base64编码
                // 使用响应生成器的Base64编码
        response.response_data_base64 = response_generator_->Base64Encode(response_data);
        
        response.timestamp = std::chrono::system_clock::now();

        // 解析响应报文的头部以获取消息ID，用于生成详细日志
        std::string response_name = "Unknown Response";

        // 确保报文长度足够解析出消息ID (偏移量6, 长度 2)
        if (response_data.size() >= 8) { 
            // 假设消息ID是小端字节序，位于偏移量为6的位置
            uint16_t response_msg_id = static_cast<uint16_t>(response_data[6]) | (static_cast<uint16_t>(response_data[7]) << 8);
            // 使用通用解析器获取消息类型名称
            response_name = GetMessageTypeName(response_msg_id);
        }
        
        // 发送到Redis队列
        bool success = mq_client_->PushResponse(config_.redis.response_queue_key, response).success;
        
        if (success) {
            Log("DEBUG", "Response sent to " + source_ip + " (" + std::to_string(response_data.size()) + " bytes): " + response_name);
        } else {
            Log("ERROR", "Failed to send response to " + source_ip);
        }
        
        return success;
        
    } catch (const std::exception& e) {
        HandleError("Exception in SendResponse: " + std::string(e.what()));
        return false;
    }
}

void MessageProcessor::Log(const std::string& level, const std::string& message) const {
    Utils::Logger::Instance().Log(level, message, "MessageProcessor");
}

void MessageProcessor::LogPerformance(uint16_t msg_id, long long processing_time_ms) {
    std::stringstream ss;
    ss << "Performance - Message " << msg_id << " (" << GetMessageTypeName(msg_id) << ") ";
    ss << "processed in " << processing_time_ms << "ms";
    
    Log("PERF", ss.str());
}

void MessageProcessor::HandleError(const std::string& error_msg) {
    Log("ERROR", error_msg);
    
    if (error_callback_) {
        error_callback_(error_msg);
    }
}

bool MessageProcessor::ShouldRespond(uint16_t msg_id) const {
    // 大部分消息都需要响应，除了某些特殊情况
    switch (msg_id) {
        case 1:   // 通用应答（设备发送的）
            return false;
        default:
            return true;
    }
}

std::string MessageProcessor::GetMessageTypeName(uint16_t msg_id) const {
    // 从配置文件中动态获取消息类型名称，避免硬编码
    if (universal_parser_) {
        try {
            // 尝试从 universal_parsing_rules.json 中获取消息类型名称
            auto message_rules = universal_parser_->GetMessageRules();
            if (message_rules.find(std::to_string(msg_id)) != message_rules.end()) {
                return message_rules[std::to_string(msg_id)]["name"];
            }
        } catch (const std::exception& e) {
            // 如果获取失败，记录错误但继续执行
            Log("WARN", "Failed to get message type name from config for msg_id " + std::to_string(msg_id) + ": " + e.what());
        }
    }
    
    // 如果无法从配置文件获取，使用默认映射（仅作为后备方案）
    switch (msg_id) {
        // 上行报文（客户端→系统）
        case 1: return "设备通用应答报文";
        case 2: return "注册报文";
        case 3: return "登录报文";
        case 4: return "设备心跳";
        case 5: return "查询升级";
        case 6: return "上传升级结果";
        case 7: return "参数上报";
        case 8: return "上传文件";
        case 9: return "文件下载";
        case 10: return "设备事件";
        case 11: return "设备日志上传";
        case 12: return "点钞信息上报";
        
        // 下行报文（系统→客户端）
        case 0x8001: return "系统通用应答报文";
        case 0x8002: return "注册应答";
        case 0x8003: return "登录应答";
        case 0x8004: return "心跳应答";
        case 0x8005: return "查询升级应答";
        case 0x8009: return "文件下载报文";
        case 0x8106: return "推送升级";
        case 0x8107: return "查询参数";
        case 0x8108: return "参数下发";
        case 0x8109: return "发送透传";
        case 0x8114: return "取消升级";
        
        default: return "Unknown";
    }
}



bool MessageProcessor::ValidateMessage(const UniversalParsedMessage& parsed_msg) const {
    if (!parsed_msg.is_valid) {
        Log("WARN", "Message validation failed: parsed message is invalid");
        return false;
    }
    
    // 获取设备ID
    std::string device_id = parsed_msg.GetField<std::string>("devUniqueId");
    if (device_id.empty()) {
        Log("WARN", "Message validation failed: device_id is empty");
        return false;
    }
    
    // 根据协议配置进行验证
    std::string protocol_id = parsed_msg.protocol_id.empty() ? "dp_protocol_v1" : parsed_msg.protocol_id;
    
    // 获取协议解析策略
    auto strategy = universal_parser_->GetProtocolStrategy(protocol_id);
    if (!strategy.has_value()) {
        Log("WARN", "Message validation failed: protocol strategy not found for " + protocol_id);
        return false;
    }
    
    const auto& protocol_strategy = strategy.value();
    
    // 1. 头部签名验证
    if (!protocol_strategy.header_signature.empty()) {
        auto msg_head_data = parsed_msg.GetField<uint16_t>("msg_head");
        uint16_t expected_header = (static_cast<uint16_t>(protocol_strategy.header_signature[1]) << 8) | 
                                  static_cast<uint16_t>(protocol_strategy.header_signature[0]);
        if (msg_head_data != expected_header) {
            Log("WARN", "Message validation failed: invalid header (expected 0x" + 
                std::to_string(expected_header) + ", got 0x" + std::to_string(msg_head_data) + ")");
            return false;
        }
    }
    
    // 2. 消息类型验证（如果协议配置中有定义）
    // 注意：这里我们不再硬编码0x03，而是根据协议配置进行验证
    
    // 3. 设备ID格式验证
    if (!parsed_msg.HasField("devUniqueId")) {
        Log("WARN", "Message validation failed: device_id field not found");
        return false;
    }
    
    // 4. CRC校验验证
    if (!parsed_msg.raw_data_base64.empty() && universal_parser_) {
        // 从Base64解码原始数据
        std::vector<uint8_t> raw_data = universal_parser_->DecodeBase64(parsed_msg.raw_data_base64);
        if (!raw_data.empty()) {
            // 检查数据包长度是否足够包含CRC和报尾
            if (raw_data.size() >= 4) {
                // 检查尾部签名
                if (!protocol_strategy.tail_signature.empty()) {
                    size_t tail_offset = raw_data.size() - protocol_strategy.tail_signature.size();
                    if (tail_offset >= 0) {
                        bool tail_match = true;
                        for (size_t i = 0; i < protocol_strategy.tail_signature.size(); ++i) {
                            if (raw_data[tail_offset + i] != protocol_strategy.tail_signature[i]) {
                                tail_match = false;
                                break;
                            }
                        }
                        if (!tail_match) {
                            Log("WARN", "Message validation failed: invalid tail signature");
                            return false;
                        }
                    }
                }
                
                // 验证CRC
                if (protocol_strategy.has_crc) {
                    if (!universal_parser_->ValidateCRC(raw_data.data(), raw_data.size())) {
                        Log("WARN", "Message validation failed: CRC check failed for msg_id: " + std::to_string(parsed_msg.msg_id));
                        return false;
                    }
                }
            } else {
                Log("WARN", "Message validation failed: raw data too short for validation");
                return false;
            }
        } else {
            Log("WARN", "Message validation failed: cannot decode raw data from Base64");
            return false;
        }
    }
    
    Log("DEBUG", "Message validation passed for msg_id: " + std::to_string(parsed_msg.msg_id) + " (protocol: " + protocol_id + ")");
    return true;
}

void MessageProcessor::UpdateLastMessageTime() {
    last_message_time_ = std::chrono::system_clock::now();
}

bool MessageProcessor::CheckQueueHealth() const {
    std::lock_guard<std::mutex> lock(const_cast<std::mutex&>(queue_mutex_));
    
    // 检查队列是否过满
    if (message_queue_.size() > config_.thread.queue_size * 0.8) {
        return false;
    }
    
    return true;
}

bool MessageProcessor::CheckRedisHealth() const {
    if (!mq_client_) {
        return false;
    }
    
    return mq_client_->IsConnected() && mq_client_->Ping().success;
}

std::string MessageProcessor::FormatTime(const std::chrono::system_clock::time_point& tp) const {
    std::time_t time = std::chrono::system_clock::to_time_t(tp);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

long long MessageProcessor::CalculateProcessingTime(const std::chrono::system_clock::time_point& start_time) const {
    auto end_time = std::chrono::system_clock::now();
    return std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
}


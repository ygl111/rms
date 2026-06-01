#include "Application.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <thread>
#include <csignal>
#include <cstdlib>
#include <filesystem>


// 静态成员初始化
Application* Application::instance_ = nullptr;

Application::Application() {
    instance_ = this;
    start_time_ = std::chrono::system_clock::now();
}

Application::~Application() {
    Stop();
    instance_ = nullptr;
}

bool Application::Initialize(const std::string& config_file) {
    Log("INFO", "Initializing C++ Parser Application...");
    
    // 加载配置
    if (!config_.LoadFromFile(config_file)) {
        Log("ERROR", "Failed to load configuration from: " + config_file);
        return false;
    }
    
    // 验证配置
    if (!ValidateConfig()) {
        Log("ERROR", "Configuration validation failed");
        return false;
    }
    
    // 检查依赖
    if (!CheckDependencies()) {
        Log("ERROR", "Dependencies check failed");
        return false;
    }
    
    // 初始化日志系统
    if (!InitializeLogging()) {
        Log("ERROR", "Failed to initialize logging");
        return false;
    }
    
    // 初始化各个组件
    if (!InitializeComponents()) {
        Log("ERROR", "Failed to initialize components");
        return false;
    }
    
    // 设置信号处理
    SetupSignalHandlers();
    
    // 打印启动信息
    PrintStartupInfo();
    
    Log("INFO", "Application initialized successfully");
    return true;
}

int Application::Run() {
    if (!message_processor_) {
        Log("ERROR", "Message processor not initialized");
        return -1;
    }
    
    Log("INFO", "Starting C++ Parser Application...");
    
    // 启动消息处理器
    if (!message_processor_->Start()) {
        Log("ERROR", "Failed to start message processor");
        return -1;
    }
    
    running_ = true;
    
    // 启动监控线程
    if (config_.monitor.enable_health_check) {
        monitor_thread_ = std::thread(&Application::MonitorThread, this);
    }
    
    // 启动统计线程
    if (config_.monitor.enable_stats) {
        stats_thread_ = std::thread(&Application::StatsThread, this);
    }
    
    Log("INFO", "Application started successfully");
    
    // 主循环
    while (running_ && !should_stop_) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        
        // 检查消息处理器状态
        if (!message_processor_->IsRunning()) {
            Log("ERROR", "Message processor stopped unexpectedly");
            break;
        }
    }
    
    // 停止应用程序
    Stop();
    
    Log("INFO", "Application stopped");
    return 0;
}

void Application::Stop() {
    if (!running_) {
        return;
    }
    
    Log("INFO", "Stopping application...");
    
    should_stop_ = true;
    running_ = false;
    
    // 停止消息处理器
    if (message_processor_) {
        message_processor_->Stop();
    }
    
    // 等待线程结束
    if (monitor_thread_.joinable()) {
        monitor_thread_.join();
    }
    
    if (stats_thread_.joinable()) {
        stats_thread_.join();
    }
    
    // 清理资源
    Cleanup();
    
    Log("INFO", "Application stopped successfully");
}

bool Application::ReloadConfig(const std::string& config_file) {
    Log("INFO", "Reloading configuration...");
    
    std::string config_path = config_file.empty() ? "parser_config.json" : config_file;
    
    ParserConfig new_config;
    if (!new_config.LoadFromFile(config_path)) {
        Log("ERROR", "Failed to load new configuration");
        return false;
    }
    
    if (!new_config.Validate()) {
        Log("ERROR", "New configuration validation failed");
        return false;
    }
    
    // 更新配置
    config_ = new_config;
    
    // 更新消息处理器配置
    if (message_processor_) {
        message_processor_->UpdateConfig(config_);
    }
    
    Log("INFO", "Configuration reloaded successfully");
    return true;
}

void Application::OverrideThreadCount(int thread_count) {
    if (thread_count > 0) {
        int old_count = config_.thread.worker_threads;
        config_.thread.worker_threads = thread_count;
        Log("INFO", "Thread count overridden: " + std::to_string(old_count) + " -> " + std::to_string(thread_count));
        
        // 更新消息处理器配置
        if (message_processor_) {
            message_processor_->UpdateConfig(config_);
        }
    } else {
        Log("WARN", "Invalid thread count ignored: " + std::to_string(thread_count));
    }
}

std::map<std::string, std::string> Application::GetStatus() const {
    std::map<std::string, std::string> status;
    
    status["running"] = running_ ? "true" : "false";
    status["uptime"] = FormatUptime();
    status["memory_usage_mb"] = std::to_string(GetMemoryUsage());
    status["cpu_usage_percent"] = std::to_string(GetCPUUsage());
    
    if (message_processor_) {
        auto processor_status = message_processor_->GetHealthStatus();
        status["processor_running"] = processor_status["running"];
        status["redis_connected"] = processor_status["redis_connected"];
        status["queue_health"] = processor_status["queue_health"];
        status["messages_processed"] = processor_status["messages_processed"];
        status["messages_failed"] = processor_status["messages_failed"];
        status["avg_processing_time_ms"] = processor_status["avg_processing_time_ms"];
    }
    
    return status;
}

std::map<std::string, long long> Application::GetPerformanceStats() const {
    if (message_processor_) {
        return message_processor_->GetStats().GetStatsMap();
    }
    return {};
}

bool Application::CreateDefaultConfig(const std::string& config_file) {
    ParserConfig default_config = ParserConfig::GetDefault();
    
    if (!default_config.SaveToFile(config_file)) {
        std::cerr << "Failed to create default configuration file: " << config_file << std::endl;
        return false;
    }
    
    std::cout << "Default configuration created: " << config_file << std::endl;
    return true;
}

void Application::ShowHelp() {
    std::cout << "C++ Parser Service\n";
    std::cout << "Usage: cpp_parser [options]\n\n";
    std::cout << "Options:\n";
    std::cout << "  -c, --config <file>     Configuration file path (default: parser_config.json)\n";
    std::cout << "  -d, --daemon            Run as daemon\n";
    std::cout << "  -h, --help              Show this help message\n";
    std::cout << "  -v, --version           Show version information\n";
    std::cout << "  --create-config <file>  Create default configuration file\n";
    std::cout << "  --validate-config       Validate configuration file\n";
    std::cout << "  --test-protocol         Test protocol parsing\n";
    std::cout << "\nExamples:\n";
    std::cout << "  cpp_parser -c config.json\n";
    std::cout << "  cpp_parser --create-config my_config.json\n";
    std::cout << "  cpp_parser --validate-config -c config.json\n";
    std::cout << "\nSignals:\n";
    std::cout << "  SIGTERM, SIGINT   Graceful shutdown\n";
    std::cout << "  SIGUSR1           Reload configuration\n";
    std::cout << "  SIGUSR2           Print statistics\n";
}

void Application::ShowVersion() {
    std::cout << "C++ Parser Service\n";
    std::cout << "Version: 1.0.0\n";
    std::cout << "Protocol: DP Protocol v1.0\n";
    std::cout << "Build: " << __DATE__ << " " << __TIME__ << "\n";
    std::cout << "Compiler: " << __VERSION__ << "\n";
}

void Application::SignalHandler(int signal) {
    if (!instance_) {
        return;
    }
    
    switch (signal) {
        case SIGTERM:
        case SIGINT:
            instance_->Log("INFO", "Received shutdown signal");
            instance_->should_stop_ = true;
            break;
        case SIGUSR1:
            instance_->Log("INFO", "Received reload signal");
            instance_->ReloadConfig();
            break;
        case SIGUSR2:
            instance_->Log("INFO", "Received stats signal");
            instance_->PrintStats();
            break;
        default:
            break;
    }
}

// 私有方法实现
void Application::SetupSignalHandlers() {
    std::signal(SIGTERM, SignalHandler);
    std::signal(SIGINT, SignalHandler);
    std::signal(SIGUSR1, SignalHandler);
    std::signal(SIGUSR2, SignalHandler);
    
    // 忽略SIGPIPE信号
    std::signal(SIGPIPE, SIG_IGN);
}

void Application::MonitorThread() {
    Log("INFO", "Monitor thread started");
    
    while (!should_stop_) {
        std::this_thread::sleep_for(std::chrono::seconds(config_.monitor.health_check_interval));
        
        if (should_stop_) break;
        
        // 执行健康检查
        if (!HealthCheck()) {
            Log("ERROR", "Health check failed");
            // 可以在这里实现故障恢复逻辑
        }
    }
    
    Log("INFO", "Monitor thread stopped");
}

void Application::StatsThread() {
    Log("INFO", "Stats thread started");
    
    while (!should_stop_) {
        std::this_thread::sleep_for(std::chrono::seconds(config_.monitor.stats_interval));
        
        if (should_stop_) break;
        
        PrintStats();
    }
    
    Log("INFO", "Stats thread stopped");
}

bool Application::InitializeLogging() {
    // 这里可以初始化日志系统
    // 例如：设置日志文件、日志级别、日志格式等
    
    if (config_.log.enable_file_log) {
        // 创建日志文件目录
        std::filesystem::path log_file_path(config_.log.log_file);
        if (log_file_path.has_parent_path()) {
            std::filesystem::create_directories(log_file_path.parent_path());
        }
    }
    
    return true;
}

bool Application::InitializeComponents() {
    try {
        // --- 1. 初始化数据库客户端 ---
        Log("INFO", "Initializing database client...");
        auto dbFactory = DPower::DB::CreateMySqlDatabaseFactory();
        db_client_ = dbFactory->Create();
        const auto& db_config = config_.database;
        auto db_conn_res = db_client_->Connect(db_config.uri, db_config.user, db_config.password);
        if (!db_conn_res.success) {
            Log("ERROR", "Failed to connect to database: " + db_conn_res.error_message);
            return false;
        }
        Log("INFO", "Database connection successful.");

        // --- 2. 初始化消息队列 (Redis) 客户端 ---
        Log("INFO", "Initializing Message Queue (Redis) client...");
        auto mqFactory = DPower::Redis::CreateSwRedisFactory();
        mq_client_ = mqFactory->Create();
        const auto& redis_config = config_.redis;
        auto mq_conn_res = mq_client_->Connect(redis_config.host, redis_config.port, redis_config.password, redis_config.db);
        if (!mq_conn_res.success) {
            Log("ERROR", "Failed to connect to Message Queue Redis: " + mq_conn_res.error_message);
            return false;
        }
        mq_client_->CreateConsumerGroup(redis_config.request_stream_key, redis_config.consumer_group);
        Log("INFO", "Message Queue client connection successful.");

        // --- 3. 初始化缓存 (Redis) 客户端 ---
        Log("INFO", "Initializing Cache (Redis) client...");
        auto cacheFactory = DPower::Cache::CreateRedisCacheFactory();
        // 创建一个全新的、独立的 Redis 实例专门给缓存使用
        auto raw_cache_redis_client = DPower::Redis::CreateSwRedisFactory()->Create();
        // 缓存连接到不同的DB，例如 redis.db + 1
        if (!raw_cache_redis_client->Connect(redis_config.host, redis_config.port, redis_config.password, redis_config.db + 1).success) { 
            Log("ERROR", "Failed to connect to Cache Redis");
            return false;
        }
        cache_client_ = cacheFactory->Create(std::move(raw_cache_redis_client));
        if (!cache_client_) {
            Log("ERROR", "Failed to create cache client.");
            return false;
        }
        Log("INFO", "Cache client initialized successfully.");

        // --- 程序启动时清除所有缓存 ---
        Log("INFO", "Clearing all cache data on startup...");
        if (cache_client_->ClearAllCache()) {
            Log("INFO", "All cache data cleared successfully on startup.");
        } else {
            Log("WARN", "Failed to clear cache data on startup, but continuing...");
        }

        // --- 程序启动时清除所有升级推送锁 ---
        Log("INFO", "Clearing all upgrade push locks on startup...");
        if (cache_client_->ClearAllUpgradeLocks()) {
            Log("INFO", "All upgrade push locks cleared successfully on startup.");
        } else {
            Log("WARN", "Failed to clear upgrade push locks on startup, but continuing...");
        }

        // ======================= [调试检查] =======================
        if (!mq_client_) {
            Log("FATAL", "mq_client_ is NULL right before creating MessageProcessor!");
            return false;
        } else {
            Log("DEBUG", "mq_client_ is VALID right before creating MessageProcessor.");
        }
        // =================================================================

        // --- 初始化消息处理器，并注入所有独立的依赖 ---
        Log("INFO", "Initializing message processor...");
        message_processor_ = std::make_shared<MessageProcessor>(
            db_client_, 
            cache_client_, 
            mq_client_, // 此时 mq_client_ 仍然是一个有效的指针
            config_.ftp
        );
        
        if (!message_processor_->Initialize(config_)) {
            Log("ERROR", "Failed to initialize message processor");
            return false;
        }
        
        message_processor_->SetErrorCallback([this](const std::string& error) {
            Log("ERROR", "Message processor error: " + error);
        });

    } catch (const std::exception& e) {
        Log("ERROR", "Exception during component initialization: " + std::string(e.what()));
        return false;
    }
    
    return true;
}

bool Application::ValidateConfig() const {
    if (!config_.Validate()) {
        return false;
    }
    
    // 额外的验证逻辑
    if (!std::filesystem::exists(config_.protocol.schema_path)) {
        Log("ERROR", "Protocol schema file not found: " + config_.protocol.schema_path);
        return false;
    }
    
    return true;
}

bool Application::CheckDependencies() const {
    // 检查必要的目录和文件
    if (!std::filesystem::exists(config_.protocol.schema_path)) {
        Log("ERROR", "Protocol schema file not found: " + config_.protocol.schema_path);
        return false;
    }
    
    // 检查日志目录
    if (config_.log.enable_file_log) {
        std::filesystem::path log_path(config_.log.log_file);
        if (log_path.has_parent_path()) {
            std::error_code ec;
            std::filesystem::create_directories(log_path.parent_path(), ec);
            if (ec) {
                Log("ERROR", "Failed to create log directory: " + ec.message());
                return false;
            }
        }
    }
    
    return true;
}

void Application::PrintStartupInfo() const {
    Log("INFO", "=== C++ Parser Service ===");
    Log("INFO", "Version: 1.0.0");
    Log("INFO", "Protocol: DP Protocol v1.0");
    Log("INFO", "Build: " + std::string(__DATE__) + " " + std::string(__TIME__));
    Log("INFO", "===========================");
    
    // 打印配置信息
    config_.PrintConfig();
}

void Application::PrintStats() const {
    if (!message_processor_) {
        return;
    }
    
    auto stats = message_processor_->GetStats().GetStatsMap();
    auto status = GetStatus();
    
    Log("INFO", "=== Performance Statistics ===");
    Log("INFO", "Uptime: " + status["uptime"]);
    Log("INFO", "Memory Usage: " + status["memory_usage_mb"] + " MB");
    Log("INFO", "CPU Usage: " + status["cpu_usage_percent"] + "%");
    Log("INFO", "Messages Processed: " + std::to_string(stats["messages_processed"]));
    Log("INFO", "Messages Failed: " + std::to_string(stats["messages_failed"]));
    Log("INFO", "Responses Generated: " + std::to_string(stats["responses_generated"]));
    Log("INFO", "Average Processing Time: " + std::to_string(stats["avg_processing_time_ms"]) + "ms");
    Log("INFO", "==============================");
}

bool Application::HealthCheck() const {
    if (!message_processor_) {
        return false;
    }
    
    return message_processor_->HealthCheck();
}

void Application::HandleExit(int exit_code) {
    Log("INFO", "Application exiting with code: " + std::to_string(exit_code));
    Stop();
}

void Application::Cleanup() {
    Log("INFO", "Cleaning up application resources...");
    
    // 只清理 Application 类拥有的资源
    message_processor_.reset();
    cache_client_.reset();
    db_client_.reset();
    mq_client_.reset();
    
    Log("INFO", "Cleanup complete.");
}

void Application::Log(const std::string& level, const std::string& message) const {
    auto now = std::chrono::system_clock::now();
    std::time_t time = std::chrono::system_clock::to_time_t(now);
    
    std::stringstream ss;
    ss << "[" << std::put_time(std::localtime(&time), "%Y-%m-%d %H:%M:%S") << "] ";
    ss << "[" << level << "] " << message;
    
    std::string log_msg = ss.str();
    
    if (config_.log.enable_console_log) {
        std::cout << log_msg << std::endl;
    }
    
    if (config_.log.enable_file_log) {
        std::ofstream log_file(config_.log.log_file, std::ios::app);
        if (log_file.is_open()) {
            log_file << log_msg << std::endl;
            log_file.close();
        }
    }
}

std::string Application::FormatUptime() const {
    auto now = std::chrono::system_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(now - start_time_);
    
    long long seconds = duration.count();
    long long days = seconds / 86400;
    seconds %= 86400;
    long long hours = seconds / 3600;
    seconds %= 3600;
    long long minutes = seconds / 60;
    seconds %= 60;
    
    std::stringstream ss;
    if (days > 0) {
        ss << days << " days, ";
    }
    ss << std::setfill('0') << std::setw(2) << hours << ":";
    ss << std::setfill('0') << std::setw(2) << minutes << ":";
    ss << std::setfill('0') << std::setw(2) << seconds;
    
    return ss.str();
}

double Application::GetMemoryUsage() const {
    // 简单的内存使用情况获取
    // 在实际应用中，可以使用更精确的方法
    std::ifstream status_file("/proc/self/status");
    std::string line;
    
    while (std::getline(status_file, line)) {
        if (line.find("VmRSS:") == 0) {
            std::istringstream iss(line);
            std::string key;
            long long value;
            std::string unit;
            
            iss >> key >> value >> unit;
            
            if (unit == "kB") {
                return value / 1024.0;  // 转换为MB
            }
        }
    }
    
    return 0.0;
}

double Application::GetCPUUsage() const {
    // 简单的CPU使用率计算
    // 在实际应用中，需要实现更精确的CPU使用率计算
    return 0.0;
} 

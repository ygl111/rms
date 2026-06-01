#include "logic/Config.h"
#include <fstream>
#include <iostream>
#include <filesystem>

bool ParserConfig::LoadFromFile(const std::string& config_file) {
    try {
        if (!std::filesystem::exists(config_file)) {
            std::cerr << "Config file not found: " << config_file << std::endl;
            return false;
        }

        std::ifstream file(config_file);
        if (!file.is_open()) {
            std::cerr << "Failed to open config file: " << config_file << std::endl;
            return false;
        }

        json j;
        file >> j;
        file.close();

        LoadFromJson(j);
        
        if (!Validate()) {
            std::cerr << "Config validation failed" << std::endl;
            return false;
        }

        std::cout << "Config loaded successfully from: " << config_file << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Error loading config: " << e.what() << std::endl;
        return false;
    }
}

bool ParserConfig::SaveToFile(const std::string& config_file) const {
    try {
        std::ofstream file(config_file);
        if (!file.is_open()) {
            std::cerr << "Failed to create config file: " << config_file << std::endl;
            return false;
        }

        json j = ToJson();
        file << j.dump(2);
        file.close();

        std::cout << "Config saved successfully to: " << config_file << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Error saving config: " << e.what() << std::endl;
        return false;
    }
}

bool ParserConfig::Validate() const {
    // 验证Redis配置
    if (redis.host.empty()) {
        std::cerr << "Redis host cannot be empty" << std::endl;
        return false;
    }
    
    if (redis.port <= 0 || redis.port > 65535) {
        std::cerr << "Invalid Redis port: " << redis.port << std::endl;
        return false;
    }
    
    if (redis.request_stream_key.empty()) {
        std::cerr << "Redis request stream key cannot be empty" << std::endl;
        return false;
    }
    
    if (redis.response_queue_key.empty()) {
        std::cerr << "Redis response queue key cannot be empty" << std::endl;
        return false;
    }
    
    if (redis.consumer_group.empty()) {
        std::cerr << "Redis consumer group cannot be empty" << std::endl;
        return false;
    }
    
    if (redis.consumer_name.empty()) {
        std::cerr << "Redis consumer name cannot be empty" << std::endl;
        return false;
    }
    
    if (redis.block_timeout < 0) {
        std::cerr << "Redis block timeout cannot be negative" << std::endl;
        return false;
    }

    // 验证线程配置
    if (thread.worker_threads <= 0) {
        std::cerr << "Worker threads must be positive" << std::endl;
        return false;
    }
    
    if (thread.batch_size <= 0) {
        std::cerr << "Batch size must be positive" << std::endl;
        return false;
    }
    
    if (thread.queue_size <= 0) {
        std::cerr << "Queue size must be positive" << std::endl;
        return false;
    }

    // 验证协议配置
    if (protocol.schema_path.empty()) {
        std::cerr << "Protocol schema path cannot be empty" << std::endl;
        return false;
    }
    
    if (protocol.max_packet_size <= 0) {
        std::cerr << "Max packet size must be positive" << std::endl;
        return false;
    }

    // 验证日志配置
    if (log.enable_file_log && log.log_file.empty()) {
        std::cerr << "Log file path cannot be empty when file logging is enabled" << std::endl;
        return false;
    }
    
    if (log.log_level != "DEBUG" && log.log_level != "INFO" && 
        log.log_level != "WARN" && log.log_level != "ERROR") {
        std::cerr << "Invalid log level: " << log.log_level << std::endl;
        return false;
    }

    // 验证监控配置
    if (monitor.stats_interval <= 0) {
        std::cerr << "Stats interval must be positive" << std::endl;
        return false;
    }
    
    if (monitor.health_check_interval <= 0) {
        std::cerr << "Health check interval must be positive" << std::endl;
        return false;
    }

    return true;
}

ParserConfig ParserConfig::GetDefault() {
    ParserConfig config;
    
    // Redis默认配置
    config.redis.host = "127.0.0.1";
    config.redis.port = 6379;
    config.redis.password = "";
    config.redis.db = 0;
    config.redis.request_stream_key = "device_raw_messages";
    config.redis.response_queue_key = "device_responses";
    config.redis.consumer_group = "parser_group";
    config.redis.consumer_name = "cpp_parser_consumer";
    config.redis.block_timeout = 100;
    
    // 线程默认配置
    config.thread.worker_threads = 4;
    config.thread.batch_size = 10;
    config.thread.queue_size = 1000;
    config.thread.enable_affinity = false;
    
    // 协议默认配置
    config.protocol.schema_path = "config/dp_protocol_v1.json";
    config.protocol.enable_crc_check = true;
    config.protocol.enable_packet_validation = true;
    config.protocol.max_packet_size = 4096;
    config.protocol.enable_schema_resolver = true;
    
    // 日志默认配置
    config.log.enable_console_log = true;
    config.log.enable_file_log = true;
    config.log.log_file = "cpp_parser.log";
    config.log.log_level = "INFO";
    config.log.enable_performance_log = false;
    
    // 监控默认配置
    config.monitor.enable_stats = true;
    config.monitor.stats_interval = 30;
    config.monitor.enable_health_check = true;
    config.monitor.health_check_interval = 60;
    
    // 数据库默认配置
    config.database.uri = "localhost:3306/rms";
    config.database.user = "rms_user";
    config.database.password = "12345678";
    
    // FTP默认配置
    config.ftp.host = "192.168.12.52";
    config.ftp.port = 21;
    config.ftp.user = "ftpuser";
    config.ftp.password = "1234";

    // 鉴权默认配置
    config.auth.server_secret_key = "DPower_Server_Secret_Key_2024";
    config.auth.auth_algorithm = "HMAC-SHA256";
    config.auth.auth_code_length = 16;

    return config;
}

void ParserConfig::PrintConfig() const {
    std::cout << "=== Parser Configuration ===" << std::endl;
    
    std::cout << "[Redis]" << std::endl;
    std::cout << "  Host: " << redis.host << std::endl;
    std::cout << "  Port: " << redis.port << std::endl;
    std::cout << "  Database: " << redis.db << std::endl;
    std::cout << "  Request Stream Key: " << redis.request_stream_key << std::endl;
    std::cout << "  Response Queue Key: " << redis.response_queue_key << std::endl;
    std::cout << "  Consumer Group: " << redis.consumer_group << std::endl;
    std::cout << "  Consumer Name: " << redis.consumer_name << std::endl;
    std::cout << "  Block Timeout: " << redis.block_timeout << "ms" << std::endl;
    
    std::cout << "[Database]" << std::endl;
    std::cout << "  URI: " << database.uri << std::endl;
    std::cout << "  User: " << database.user << std::endl;
    std::cout << "  Password: " << (database.password.empty() ? "<empty>" : "***") << std::endl;
    
    std::cout << "[FTP]" << std::endl;
    std::cout << "  Host: " << ftp.host << std::endl;
    std::cout << "  Port: " << ftp.port << std::endl;
    std::cout << "  User: " << ftp.user << std::endl;
    std::cout << "  Password: " << (ftp.password.empty() ? "<empty>" : "***") << std::endl;
    
    std::cout << "[Thread]" << std::endl;
    std::cout << "  Worker Threads: " << thread.worker_threads << std::endl;
    std::cout << "  Batch Size: " << thread.batch_size << std::endl;
    std::cout << "  Queue Size: " << thread.queue_size << std::endl;
    std::cout << "  Enable Affinity: " << (thread.enable_affinity ? "Yes" : "No") << std::endl;
    
    std::cout << "[Protocol]" << std::endl;
    std::cout << "  Schema Path: " << protocol.schema_path << std::endl;
    std::cout << "  Enable CRC Check: " << (protocol.enable_crc_check ? "Yes" : "No") << std::endl;
    std::cout << "  Enable Packet Validation: " << (protocol.enable_packet_validation ? "Yes" : "No") << std::endl;
    std::cout << "  Max Packet Size: " << protocol.max_packet_size << " bytes" << std::endl;
    std::cout << "  Enable Schema Resolver: " << (protocol.enable_schema_resolver ? "Yes" : "No") << std::endl;
    
    std::cout << "[Log]" << std::endl;
    std::cout << "  Enable Console Log: " << (log.enable_console_log ? "Yes" : "No") << std::endl;
    std::cout << "  Enable File Log: " << (log.enable_file_log ? "Yes" : "No") << std::endl;
    std::cout << "  Log File: " << log.log_file << std::endl;
    std::cout << "  Log Level: " << log.log_level << std::endl;
    std::cout << "  Enable Performance Log: " << (log.enable_performance_log ? "Yes" : "No") << std::endl;
    
    std::cout << "[Monitor]" << std::endl;
    std::cout << "  Enable Stats: " << (monitor.enable_stats ? "Yes" : "No") << std::endl;
    std::cout << "  Stats Interval: " << monitor.stats_interval << "s" << std::endl;
    std::cout << "  Enable Health Check: " << (monitor.enable_health_check ? "Yes" : "No") << std::endl;
    std::cout << "  Health Check Interval: " << monitor.health_check_interval << "s" << std::endl;
    
    std::cout << "[Auth]" << std::endl;
    std::cout << "  Server Secret Key: " << (auth.server_secret_key.empty() ? "<empty>" : "***") << std::endl;
    std::cout << "  Auth Algorithm: " << auth.auth_algorithm << std::endl;
    std::cout << "  Auth Code Length: " << auth.auth_code_length << " bytes" << std::endl;
    
    std::cout << "===========================" << std::endl;
}

void ParserConfig::LoadFromJson(const json& j) {
    // 加载Redis配置
    if (j.contains("redis")) {
        const auto& redis_json = j["redis"];
        if (redis_json.contains("host")) redis.host = redis_json["host"];
        if (redis_json.contains("port")) redis.port = redis_json["port"];
        if (redis_json.contains("password")) redis.password = redis_json["password"];
        if (redis_json.contains("db")) redis.db = redis_json["db"];
        if (redis_json.contains("request_stream_key")) redis.request_stream_key = redis_json["request_stream_key"];
        if (redis_json.contains("response_queue_key")) redis.response_queue_key = redis_json["response_queue_key"];
        if (redis_json.contains("consumer_group")) redis.consumer_group = redis_json["consumer_group"];
        if (redis_json.contains("consumer_name")) redis.consumer_name = redis_json["consumer_name"];
        if (redis_json.contains("block_timeout")) redis.block_timeout = redis_json["block_timeout"];
    }

    // 加载数据库配置
    if (j.contains("database")) {
        const auto& db_json = j["database"];
        if (db_json.contains("uri")) database.uri = db_json["uri"];
        if (db_json.contains("user")) database.user = db_json["user"];
        if (db_json.contains("password")) database.password = db_json["password"];
    }

    // 加载FTP配置
    if (j.contains("ftp")) {
        const auto& ftp_json = j["ftp"];
        if (ftp_json.contains("host")) ftp.host = ftp_json["host"];
        if (ftp_json.contains("port")) ftp.port = ftp_json["port"];
        if (ftp_json.contains("user")) ftp.user = ftp_json["user"];
        if (ftp_json.contains("password")) ftp.password = ftp_json["password"];
    }

    // 加载线程配置
    if (j.contains("thread")) {
        const auto& thread_json = j["thread"];
        if (thread_json.contains("worker_threads")) thread.worker_threads = thread_json["worker_threads"];
        if (thread_json.contains("batch_size")) thread.batch_size = thread_json["batch_size"];
        if (thread_json.contains("queue_size")) thread.queue_size = thread_json["queue_size"];
        if (thread_json.contains("enable_affinity")) thread.enable_affinity = thread_json["enable_affinity"];
    }

    // 加载协议配置
    if (j.contains("protocol")) {
        const auto& protocol_json = j["protocol"];
        if (protocol_json.contains("schema_path")) protocol.schema_path = protocol_json["schema_path"];
        if (protocol_json.contains("enable_crc_check")) protocol.enable_crc_check = protocol_json["enable_crc_check"];
        if (protocol_json.contains("enable_packet_validation")) protocol.enable_packet_validation = protocol_json["enable_packet_validation"];
        if (protocol_json.contains("max_packet_size")) protocol.max_packet_size = protocol_json["max_packet_size"];
        if (protocol_json.contains("enable_schema_resolver")) protocol.enable_schema_resolver = protocol_json["enable_schema_resolver"];
    }

    // 加载日志配置
    if (j.contains("log")) {
        const auto& log_json = j["log"];
        if (log_json.contains("enable_console_log")) log.enable_console_log = log_json["enable_console_log"];
        if (log_json.contains("enable_file_log")) log.enable_file_log = log_json["enable_file_log"];
        if (log_json.contains("log_file")) log.log_file = log_json["log_file"];
        if (log_json.contains("log_level")) log.log_level = log_json["log_level"];
        if (log_json.contains("enable_performance_log")) log.enable_performance_log = log_json["enable_performance_log"];
    }

    // 加载监控配置
    if (j.contains("monitor")) {
        const auto& monitor_json = j["monitor"];
        if (monitor_json.contains("enable_stats")) monitor.enable_stats = monitor_json["enable_stats"];
        if (monitor_json.contains("stats_interval")) monitor.stats_interval = monitor_json["stats_interval"];
        if (monitor_json.contains("enable_health_check")) monitor.enable_health_check = monitor_json["enable_health_check"];
        if (monitor_json.contains("health_check_interval")) monitor.health_check_interval = monitor_json["health_check_interval"];
    }

    // 加载鉴权配置
    if (j.contains("auth")) {
        const auto& auth_json = j["auth"];
        if (auth_json.contains("server_secret_key")) auth.server_secret_key = auth_json["server_secret_key"];
        if (auth_json.contains("auth_algorithm")) auth.auth_algorithm = auth_json["auth_algorithm"];
        if (auth_json.contains("auth_code_length")) auth.auth_code_length = auth_json["auth_code_length"];
    }
}

json ParserConfig::ToJson() const {
    json j;
    
    // Redis配置
    j["redis"]["host"] = redis.host;
    j["redis"]["port"] = redis.port;
    j["redis"]["password"] = redis.password;
    j["redis"]["db"] = redis.db;
    j["redis"]["request_stream_key"] = redis.request_stream_key;
    j["redis"]["response_queue_key"] = redis.response_queue_key;
    j["redis"]["consumer_group"] = redis.consumer_group;
    j["redis"]["consumer_name"] = redis.consumer_name;
    j["redis"]["block_timeout"] = redis.block_timeout;
    
    // 数据库配置
    j["database"]["uri"] = database.uri;
    j["database"]["user"] = database.user;
    j["database"]["password"] = database.password;
    
    // FTP配置
    j["ftp"]["host"] = ftp.host;
    j["ftp"]["port"] = ftp.port;
    j["ftp"]["user"] = ftp.user;
    j["ftp"]["password"] = ftp.password;
    
    // 线程配置
    j["thread"]["worker_threads"] = thread.worker_threads;
    j["thread"]["batch_size"] = thread.batch_size;
    j["thread"]["queue_size"] = thread.queue_size;
    j["thread"]["enable_affinity"] = thread.enable_affinity;
    
    // 协议配置
    j["protocol"]["schema_path"] = protocol.schema_path;
    j["protocol"]["enable_crc_check"] = protocol.enable_crc_check;
    j["protocol"]["enable_packet_validation"] = protocol.enable_packet_validation;
    j["protocol"]["max_packet_size"] = protocol.max_packet_size;
    j["protocol"]["enable_schema_resolver"] = protocol.enable_schema_resolver;
    
    // 日志配置
    j["log"]["enable_console_log"] = log.enable_console_log;
    j["log"]["enable_file_log"] = log.enable_file_log;
    j["log"]["log_file"] = log.log_file;
    j["log"]["log_level"] = log.log_level;
    j["log"]["enable_performance_log"] = log.enable_performance_log;
    
    // 监控配置
    j["monitor"]["enable_stats"] = monitor.enable_stats;
    j["monitor"]["stats_interval"] = monitor.stats_interval;
    j["monitor"]["enable_health_check"] = monitor.enable_health_check;
    j["monitor"]["health_check_interval"] = monitor.health_check_interval;
    
    // 鉴权配置
    j["auth"]["server_secret_key"] = auth.server_secret_key;
    j["auth"]["auth_algorithm"] = auth.auth_algorithm;
    j["auth"]["auth_code_length"] = auth.auth_code_length;
    
    return j;
}
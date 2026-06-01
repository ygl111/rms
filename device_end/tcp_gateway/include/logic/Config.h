#pragma once
#include <string>
#include <map>
#include <vector>

struct AppConfig {
    // Server配置
    std::vector<std::pair<int, std::string>> listen_ports; // 端口:协议名称
    int default_port;
    int max_connections;
    int connection_timeout;
    int message_boundary_timeout;
    int license_watchdog_interval_seconds;
    bool enable_license_check;
    
    // Redis配置
    std::string redis_host;
    int redis_port;
    int redis_connection_pool_size;
    int redis_connection_timeout;
    int redis_operation_timeout;
    std::string redis_stream_key_request;
    std::string redis_queue_name_response;
    std::string redis_password;
    
    // Protocol配置
    std::string protocol_registry_file;
    std::string default_protocol;
    int protocol_identification_timeout;
    
    // Logging配置
    std::string log_level;
    bool enable_console_log;
    bool enable_file_log;
    std::string log_file_path;
    int log_file_max_size;
    int log_file_retention_days;
    
    // Performance配置
    int worker_threads;
    int batch_size;
    int queue_size;
    int heartbeat_interval;
    int offline_detection_interval;
    
    // Security配置
    bool enable_ip_whitelist;
    std::string whitelist_file;
    int max_message_size;
    bool enable_message_validation;
    
    // Monitoring配置
    bool enable_performance_monitoring;
    int stats_interval;
    int health_check_interval;
    bool enable_detailed_stats;
    
    // 构造函数，设置默认值
    AppConfig() : 
        default_port(8081),
        max_connections(1000),
        connection_timeout(300),
        message_boundary_timeout(5000),
        license_watchdog_interval_seconds(1),
        enable_license_check(true),
        redis_host("127.0.0.1"),
        redis_port(6379),
        redis_connection_pool_size(10),
        redis_connection_timeout(5000),
        redis_operation_timeout(3000),
        redis_stream_key_request("device_raw_messages"),
        redis_queue_name_response("device_responses"),
        protocol_registry_file("config/protocol_registry.json"),
        default_protocol("dp_protocol_v1"),
        protocol_identification_timeout(1000),
        log_level("INFO"),
        enable_console_log(true),
        enable_file_log(false),
        log_file_path("/var/log/tcp_gateway/gateway.log"),
        log_file_max_size(100),
        log_file_retention_days(7),
        worker_threads(0),
        batch_size(10),
        queue_size(1000),
        heartbeat_interval(30),
        offline_detection_interval(60),
        enable_ip_whitelist(false),
        whitelist_file("config/ip_whitelist.txt"),
        max_message_size(65536),
        enable_message_validation(true),
        enable_performance_monitoring(true),
        stats_interval(60),
        health_check_interval(30),
        enable_detailed_stats(false) {}
};

class Config {
public:
    // 加载配置文件并返回配置结构体
    static AppConfig load(const std::string& filename);
    
    // 解析端口列表字符串
    static std::vector<std::pair<int, std::string>> parsePortList(const std::string& port_list_str);
    
    // 验证配置
    static bool validate(const AppConfig& config);
};

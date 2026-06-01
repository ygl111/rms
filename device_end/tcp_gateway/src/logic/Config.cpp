#include "logic/Config.h"
#include <string>
#include <fstream>
#include <stdexcept>
#include <algorithm> // 用于 trim 函数
#include <sstream>
#include "logic/utils/Logger.h"

// -- 以下是用于去除字符串前后空白字符的辅助函数 --

// 去除左边空白
static inline void ltrim(std::string &s) {
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](unsigned char ch) {
        return !std::isspace(ch);
    }));
}

// 去除右边空白
static inline void rtrim(std::string &s) {
    s.erase(std::find_if(s.rbegin(), s.rend(), [](unsigned char ch) {
        return !std::isspace(ch);
    }).base(), s.end());
}

// 去除两端空白
static inline void trim(std::string &s) {
    ltrim(s);
    rtrim(s);
}

// 解析布尔值
static bool parseBool(const std::string& value) {
    std::string lower_value = value;
    std::transform(lower_value.begin(), lower_value.end(), lower_value.begin(), ::tolower);
    return lower_value == "true" || lower_value == "1" || lower_value == "yes" || lower_value == "on";
}

// -- Config::load 方法的实现 --

AppConfig Config::load(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Config file not found or could not be opened: " + filename);
    }

    AppConfig config{};
    std::string line;
    std::string current_section;

    while (std::getline(file, line)) {
        trim(line); // 去除行首尾的空白

        if (line.empty() || line[0] == '#') { // 跳过空行和注释
            continue;
        }

        if (line[0] == '[' && line.back() == ']') { // 解析节(Section)
            current_section = line.substr(1, line.length() - 2);
        } else {
            size_t delimiter_pos = line.find('=');
            if (delimiter_pos != std::string::npos) {
                std::string key = line.substr(0, delimiter_pos);
                std::string value = line.substr(delimiter_pos + 1);
                trim(key);
                trim(value);

                // 根据节和键来填充配置结构体
                if (current_section == "Server") {
                    if (key == "listen_ports") {
                        config.listen_ports = parsePortList(value);
                    } else if (key == "default_port") {
                        config.default_port = std::stoi(value);
                    } else if (key == "max_connections") {
                        config.max_connections = std::stoi(value);
                    } else if (key == "connection_timeout") {
                        config.connection_timeout = std::stoi(value);
                    } else if (key == "message_boundary_timeout") {
                        config.message_boundary_timeout = std::stoi(value);
                    } else if (key == "license_watchdog_interval_seconds") {
                        config.license_watchdog_interval_seconds = std::stoi(value);
                    } else if (key == "enable_license_check") {
                        config.enable_license_check = parseBool(value);
                    }
                } else if (current_section == "Redis") {
                    if (key == "host") {
                        config.redis_host = value;
                    } else if (key == "port") {
                        config.redis_port = std::stoi(value);
                    } else if (key == "connection_pool_size") {
                        config.redis_connection_pool_size = std::stoi(value);
                    } else if (key == "connection_timeout") {
                        config.redis_connection_timeout = std::stoi(value);
                    } else if (key == "operation_timeout") {
                        config.redis_operation_timeout = std::stoi(value);
                    } else if (key == "request_stream_key") {
                        config.redis_stream_key_request = value;
                    } else if (key == "response_queue_key") {
                        config.redis_queue_name_response = value;
                    } else if (key == "password") {
                        config.redis_password = value;
                    }
                } else if (current_section == "Protocol") {
                    if (key == "registry_file") {
                        config.protocol_registry_file = value;
                    } else if (key == "default_protocol") {
                        config.default_protocol = value;
                    } else if (key == "identification_timeout") {
                        config.protocol_identification_timeout = std::stoi(value);
                    }
                } else if (current_section == "Logging") {
                    if (key == "log_level") {
                        config.log_level = value;
                    } else if (key == "enable_console_log") {
                        config.enable_console_log = parseBool(value);
                    } else if (key == "enable_file_log") {
                        config.enable_file_log = parseBool(value);
                    } else if (key == "log_file_path") {
                        config.log_file_path = value;
                    } else if (key == "log_file_max_size") {
                        config.log_file_max_size = std::stoi(value);
                    } else if (key == "log_file_retention_days") {
                        config.log_file_retention_days = std::stoi(value);
                    }
                } else if (current_section == "Performance") {
                    if (key == "worker_threads") {
                        config.worker_threads = std::stoi(value);
                    } else if (key == "batch_size") {
                        config.batch_size = std::stoi(value);
                    } else if (key == "queue_size") {
                        config.queue_size = std::stoi(value);
                    } else if (key == "heartbeat_interval") {
                        config.heartbeat_interval = std::stoi(value);
                    } else if (key == "offline_detection_interval") {
                        config.offline_detection_interval = std::stoi(value);
                    }
                } else if (current_section == "Security") {
                    if (key == "enable_ip_whitelist") {
                        config.enable_ip_whitelist = parseBool(value);
                    } else if (key == "whitelist_file") {
                        config.whitelist_file = value;
                    } else if (key == "max_message_size") {
                        config.max_message_size = std::stoi(value);
                    } else if (key == "enable_message_validation") {
                        config.enable_message_validation = parseBool(value);
                    }
                } else if (current_section == "Monitoring") {
                    if (key == "enable_performance_monitoring") {
                        config.enable_performance_monitoring = parseBool(value);
                    } else if (key == "stats_interval") {
                        config.stats_interval = std::stoi(value);
                    } else if (key == "health_check_interval") {
                        config.health_check_interval = std::stoi(value);
                    } else if (key == "enable_detailed_stats") {
                        config.enable_detailed_stats = parseBool(value);
                    }
                }
            }
        }
    }

    file.close();

    // 验证配置
    if (!validate(config)) {
        throw std::runtime_error("Configuration validation failed");
    }
    
    return config;
}

// 解析端口列表字符串
std::vector<std::pair<int, std::string>> Config::parsePortList(const std::string& port_list_str) {
    std::vector<std::pair<int, std::string>> result;
    std::stringstream ss(port_list_str);
    std::string item;
    
    while (std::getline(ss, item, ',')) {
        trim(item);
        if (item.empty()) continue;
        
        size_t colon_pos = item.find(':');
        if (colon_pos != std::string::npos) {
            std::string port_str = item.substr(0, colon_pos);
            std::string protocol = item.substr(colon_pos + 1);
            trim(port_str);
            trim(protocol);
            
            try {
                int port = std::stoi(port_str);
                result.emplace_back(port, protocol);
            } catch (const std::exception& e) {
                Utils::Logger::Instance().Log("WARN", "Invalid port number in port list: " + port_str, "Config");
            }
        } else {
            // 如果没有协议名称，使用默认协议
            try {
                int port = std::stoi(item);
                result.emplace_back(port, "default");
            } catch (const std::exception& e) {
                Utils::Logger::Instance().Log("WARN", "Invalid port number in port list: " + item, "Config");
            }
        }
    }
    
    return result;
}

// 验证配置
bool Config::validate(const AppConfig& config) {
    // 检查必要的配置项
    if (config.redis_host.empty()) {
        Utils::Logger::Instance().Log("ERROR", "Redis host is not configured", "Config");
        return false;
    }
    
    if (config.redis_port <= 0 || config.redis_port > 65535) {
        Utils::Logger::Instance().Log("ERROR", "Invalid Redis port: " + std::to_string(config.redis_port), "Config");
        return false;
    }
    
    if (config.redis_stream_key_request.empty()) {
        Utils::Logger::Instance().Log("ERROR", "Redis request stream key is not configured", "Config");
        return false;
    }
    
    if (config.redis_queue_name_response.empty()) {
        Utils::Logger::Instance().Log("ERROR", "Redis response queue key is not configured", "Config");
        return false;
    }
    
    // 检查端口配置
    if (config.listen_ports.empty()) {
        Utils::Logger::Instance().Log("WARN", "No listen ports configured, using default port: " + std::to_string(config.default_port), "Config");
    }
    
    // 检查性能配置
    if (config.max_connections <= 0) {
        Utils::Logger::Instance().Log("ERROR", "Invalid max_connections: " + std::to_string(config.max_connections), "Config");
        return false;
    }
    
    if (config.batch_size <= 0) {
        Utils::Logger::Instance().Log("ERROR", "Invalid batch_size: " + std::to_string(config.batch_size), "Config");
        return false;
    }
    
    if (config.queue_size <= 0) {
        Utils::Logger::Instance().Log("ERROR", "Invalid queue_size: " + std::to_string(config.queue_size), "Config");
        return false;
    }

    if (config.license_watchdog_interval_seconds <= 0) {
        Utils::Logger::Instance().Log(
            "ERROR",
            "Invalid license_watchdog_interval_seconds: " + std::to_string(config.license_watchdog_interval_seconds),
            "Config");
        return false;
    }
    
    return true;
}

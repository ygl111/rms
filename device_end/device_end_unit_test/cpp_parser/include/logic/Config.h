#pragma once

#include <string>
#include <vector>
#include <memory>
#include <json.hpp>

using json = nlohmann::json;

/**
 * @brief 解析器配置类
 */
class ParserConfig {
public:
    struct RedisConfig {
        std::string host = "127.0.0.1";
        int port = 6379;
        std::string password = "";
        int db = 0;
        std::string request_stream_key = "device_raw_messages";
        std::string response_queue_key = "device_responses";
        std::string consumer_group = "parser_group";
        std::string consumer_name = "parser_consumer";
        int block_timeout = 100;  // 毫秒
    };

    /**
     * @brief 数据库配置
     */
    struct DatabaseConfig {
        std::string uri = "localhost:3306/rms";
        std::string user = "rms_user";
        std::string password = "12345678"; // 【重要】请务必替换为自己的数据库密码
    };

    /**
     * @brief FTP服务器认证配置
     */
    struct FtpConfig {
        std::string host = "192.168.12.52";
        int port = 21;
        std::string user = "ftpuser";
        std::string password = "1234";
    };

    struct ThreadConfig {
        int worker_threads = 4;
        int batch_size = 10;
        int queue_size = 1000;
        bool enable_affinity = false;
    };

    struct ProtocolConfig {
        std::string schema_path = "config/dp_protocol_v1.json";
        bool enable_crc_check = true;
        bool enable_packet_validation = true;
        int max_packet_size = 4096;
        bool enable_schema_resolver = true; // 新增：是否启用基于schema的偏移推导
    };

    struct LogConfig {
        bool enable_console_log = true;
        bool enable_file_log = true;
        std::string log_file = "cpp_parser.log";
        std::string log_level = "INFO";
        bool enable_performance_log = false;
    };

    struct MonitorConfig {
        bool enable_stats = true;
        int stats_interval = 300;  // 秒
        bool enable_health_check = true;
        int health_check_interval = 600;  // 秒
    };

    struct AuthConfig {
        std::string server_secret_key = "DPower_Server_Secret_Key_2024";
        std::string auth_algorithm = "HMAC-SHA256";
        int auth_code_length = 16;  // 鉴权码长度（字节）
    };

public:
    RedisConfig redis;
    DatabaseConfig database;
    FtpConfig ftp;
    ThreadConfig thread;
    ProtocolConfig protocol;
    LogConfig log;
    MonitorConfig monitor;
    AuthConfig auth;

    /**
     * @brief 从JSON文件加载配置
     * @param config_file 配置文件路径
     * @return 是否加载成功
     */
    bool LoadFromFile(const std::string& config_file);

    /**
     * @brief 保存配置到JSON文件
     * @param config_file 配置文件路径
     * @return 是否保存成功
     */
    bool SaveToFile(const std::string& config_file) const;

    /**
     * @brief 验证配置有效性
     * @return 是否有效
     */
    bool Validate() const;

    /**
     * @brief 获取默认配置
     * @return 默认配置实例
     */
    static ParserConfig GetDefault();

    /**
     * @brief 打印配置信息
     */
    void PrintConfig() const;

private:
    /**
     * @brief 从JSON对象加载配置
     * @param j JSON对象
     */
    void LoadFromJson(const json& j);

    /**
     * @brief 转换为JSON对象
     * @return JSON对象
     */
    json ToJson() const;
};

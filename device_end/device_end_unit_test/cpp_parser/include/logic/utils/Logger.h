#pragma once

#include <string>
#include <mutex>

namespace Utils {

class Logger {
public:
    static Logger& Instance();

    // 初始化全局日志配置
    void Initialize(bool enable_console,
                    bool enable_file,
                    const std::string& log_file,
                    const std::string& min_level);

    // 返回是否应当输出该级别日志
    bool ShouldLog(const std::string& level) const;

    // 输出日志（线程安全）。可选组件名用于模块标识（如 DeviceService 等）
    void Log(const std::string& level, const std::string& message, const char* component = nullptr);

    // 便捷方法：设置最小级别
    void SetLevel(const std::string& min_level);

private:
    Logger() = default;
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    int LevelToInt(const std::string& level) const;
    std::string NowString() const;

private:
    bool enable_console_ = true;
    bool enable_file_ = false;
    std::string log_file_ = "cpp_parser.log";
    int min_level_ = 20; // INFO 默认
    mutable std::mutex mtx_;
};

} // namespace Utils

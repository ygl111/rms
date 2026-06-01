#pragma once

#include <memory>
#include <mutex>
#include <string>

#include <spdlog/common.h>

namespace spdlog {
class logger;
}

namespace Utils {

class Logger {
public:
    static Logger& Instance();
    ~Logger();

    void Initialize(bool enable_console,
                    bool enable_file,
                    const std::string& log_file,
                    const std::string& min_level);

    bool ShouldLog(const std::string& level) const;

    void Log(const std::string& level, const std::string& message, const char* component = nullptr);

    void SetLevel(const std::string& min_level);

private:
    Logger() = default;
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    int LevelToInt(const std::string& level) const;
    spdlog::level::level_enum ToSpdLevel(const std::string& level) const;

private:
    bool enable_console_ = true;
    bool enable_file_ = false;
    std::string log_file_ = "gateway.log";
    int min_level_ = 20;
    mutable std::mutex mtx_;
    std::shared_ptr<spdlog::logger> logger_;
    bool spdlog_pool_inited_ = false;
};

}  // namespace Utils

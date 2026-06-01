#include "logic/utils/Logger.h"

#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <algorithm>

namespace Utils {

static std::string upper(const std::string& s) {
    std::string t = s;
    std::transform(t.begin(), t.end(), t.begin(), [](unsigned char c){ return static_cast<char>(std::toupper(c)); });
    return t;
}

Logger& Logger::Instance() {
    static Logger inst;
    return inst;
}

void Logger::Initialize(bool enable_console,
                        bool enable_file,
                        const std::string& log_file,
                        const std::string& min_level) {
    std::lock_guard<std::mutex> lock(mtx_);
    enable_console_ = enable_console;
    enable_file_ = enable_file;
    log_file_ = log_file;
    min_level_ = LevelToInt(upper(min_level));
}

void Logger::SetLevel(const std::string& min_level) {
    std::lock_guard<std::mutex> lock(mtx_);
    min_level_ = LevelToInt(upper(min_level));
}

bool Logger::ShouldLog(const std::string& level) const {
    return LevelToInt(upper(level)) >= min_level_;
}

int Logger::LevelToInt(const std::string& level) const {
    // 常见级别映射：DEBUG(10) < INFO(20) < WARN(30) < ERROR(40) < FATAL(50) < PERF(25)
    if (level == "DEBUG") return 10;
    if (level == "INFO")  return 20;
    if (level == "PERF")  return 25; // 介于 INFO 与 WARN 之间
    if (level == "WARN" || level == "WARNING") return 30;
    if (level == "ERROR") return 40;
    if (level == "FATAL") return 50;
    return 20; // 默认 INFO
}

std::string Logger::NowString() const {
    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#if defined(_WIN32)
    localtime_s(&tm, &t);
#else
    tm = *std::localtime(&t);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    return oss.str();
}

void Logger::Log(const std::string& level, const std::string& message, const char* component) {
    if (!ShouldLog(level)) return; // 先过滤

    std::ostringstream ss;
    ss << "[" << NowString() << "] [" << upper(level) << "] ";
    if (component && *component) {
        ss << "[" << component << "] ";
    }
    ss << message;
    const std::string line = ss.str();

    std::lock_guard<std::mutex> lock(mtx_);
    if (enable_console_) {
        std::cout << line << std::endl;
    }
    if (enable_file_) {
        std::ofstream ofs(log_file_, std::ios::app);
        if (ofs.is_open()) {
            ofs << line << std::endl;
        }
    }
}

} // namespace Utils

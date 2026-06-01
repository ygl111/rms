#include "logic/utils/Logger.h"

#include <algorithm>

#include <spdlog/async.h>
#include <spdlog/sinks/basic_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

namespace Utils {

static std::string upper(const std::string& s) {
    std::string t = s;
    std::transform(t.begin(), t.end(), t.begin(), [](unsigned char c) {
        return static_cast<char>(std::toupper(c));
    });
    return t;
}

Logger& Logger::Instance() {
    static Logger inst;
    return inst;
}

Logger::~Logger() {
    std::lock_guard<std::mutex> lock(mtx_);
    if (logger_) {
        logger_->flush();
        spdlog::drop(logger_->name());
        logger_.reset();
    }
    spdlog::shutdown();
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

    if (logger_) {
        logger_->flush();
        spdlog::drop(logger_->name());
        logger_.reset();
    }

    if (!enable_console_ && !enable_file_) {
        return;
    }

    if (!spdlog_pool_inited_) {
        spdlog::init_thread_pool(8192, 1);
        spdlog_pool_inited_ = true;
    }

    std::vector<spdlog::sink_ptr> sinks;
    if (enable_console_) {
        sinks.push_back(std::make_shared<spdlog::sinks::stdout_color_sink_mt>());
    }
    if (enable_file_) {
        sinks.push_back(std::make_shared<spdlog::sinks::basic_file_sink_mt>(log_file_, true));
    }

    logger_ = std::make_shared<spdlog::async_logger>(
        "tcp_gateway_async",
        sinks.begin(),
        sinks.end(),
        spdlog::thread_pool(),
        spdlog::async_overflow_policy::overrun_oldest);

    logger_->set_pattern("[%Y-%m-%d %H:%M:%S] [%^%l%$] %v");
    logger_->set_level(ToSpdLevel(min_level));
    logger_->flush_on(spdlog::level::err);
}

void Logger::SetLevel(const std::string& min_level) {
    std::lock_guard<std::mutex> lock(mtx_);
    min_level_ = LevelToInt(upper(min_level));
}

bool Logger::ShouldLog(const std::string& level) const {
    return LevelToInt(upper(level)) >= min_level_;
}

int Logger::LevelToInt(const std::string& level) const {
    if (level == "DEBUG") return 10;
    if (level == "INFO") return 20;
    if (level == "PERF") return 25;
    if (level == "WARN" || level == "WARNING") return 30;
    if (level == "ERROR") return 40;
    if (level == "FATAL") return 50;
    return 20;
}

void Logger::Log(const std::string& level, const std::string& message, const char* component) {
    if (!ShouldLog(level)) {
        return;
    }

    std::shared_ptr<spdlog::logger> local_logger;
    {
        std::lock_guard<std::mutex> lock(mtx_);
        local_logger = logger_;
    }
    if (!local_logger) {
        return;
    }

    if (component && *component) {
        local_logger->log(ToSpdLevel(level), "[{}] {}", component, message);
    } else {
        local_logger->log(ToSpdLevel(level), "{}", message);
    }
}

spdlog::level::level_enum Logger::ToSpdLevel(const std::string& level) const {
    const std::string lv = upper(level);
    if (lv == "DEBUG") return spdlog::level::debug;
    if (lv == "INFO") return spdlog::level::info;
    if (lv == "PERF") return spdlog::level::info;
    if (lv == "WARN" || lv == "WARNING") return spdlog::level::warn;
    if (lv == "ERROR") return spdlog::level::err;
    if (lv == "FATAL") return spdlog::level::critical;
    return spdlog::level::info;
}

}  // namespace Utils

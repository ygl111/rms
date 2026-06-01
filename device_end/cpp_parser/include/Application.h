#pragma once

#include <string>
#include <vector>
#include <memory>
#include <atomic>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <signal.h>

#include "logic/Config.h"
#include "logic/MessageProcessor.h"

#include "logic/ResponseGenerator.h"

#include "dpower/db/Interfaces.h"
#include "dpower/cache/Interfaces.h"
#include "dpower/redis/Interfaces.h"
#include "dpower/mq/Interfaces.h"

/**
 * @brief 应用程序主类
 */
class Application {
public:
    /**
     * @brief 构造函数
     */
    Application();

    /**
     * @brief 析构函数
     */
    ~Application();

    /**
     * @brief 初始化应用程序
     * @param config_file 配置文件路径
     * @return 是否成功
     */
    bool Initialize(const std::string& config_file = "parser_config.json");

    /**
     * @brief 运行应用程序
     * @return 退出码
     */
    int Run();

    /**
     * @brief 停止应用程序
     */
    void Stop();

    /**
     * @brief 重载配置
     * @param config_file 配置文件路径
     * @return 是否成功
     */
    bool ReloadConfig(const std::string& config_file = "");

    /**
     * @brief 覆盖线程数设置（必须在Initialize之后，Run之前调用）
     * @param thread_count 线程数
     */
    void OverrideThreadCount(int thread_count);

    /**
     * @brief 获取应用程序状态
     * @return 状态信息
     */
    std::map<std::string, std::string> GetStatus() const;

    /**
     * @brief 获取性能统计
     * @return 性能统计信息
     */
    std::map<std::string, long long> GetPerformanceStats() const;

    /**
     * @brief 创建默认配置文件
     * @param config_file 配置文件路径
     * @return 是否成功
     */
    static bool CreateDefaultConfig(const std::string& config_file = "parser_config.json");

    /**
     * @brief 显示帮助信息
     */
    static void ShowHelp();

    /**
     * @brief 显示版本信息
     */
    static void ShowVersion();

    /**
     * @brief 信号处理函数
     * @param signal 信号
     */
    static void SignalHandler(int signal);

private:
    static Application* instance_;
    
    ParserConfig config_;
    std::shared_ptr<MessageProcessor> message_processor_;
    
    // 使用抽象接口指针，以支持技术热插拔
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client_;
    std::shared_ptr<DPower::MQ::DPowerMqClient> rabbitmq_client_;
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client_;
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client_;
    
    std::atomic<bool> running_{false};
    std::atomic<bool> should_stop_{false};
    
    std::thread monitor_thread_;
    std::thread stats_thread_;
    mutable std::mutex stop_mutex_;
    std::condition_variable stop_cv_;
    
    // 启动时间
    std::chrono::system_clock::time_point start_time_;
    
    
    /**
     * @brief 设置信号处理
     */
    void SetupSignalHandlers();

    /**
     * @brief 监控线程
     */
    void MonitorThread();

    /**
     * @brief 统计线程
     */
    void StatsThread();

    /**
     * @brief 初始化日志系统
     * @return 是否成功
     */
    bool InitializeLogging();

    /**
     * @brief 初始化各个组件
     * @return 是否成功
     */
    bool InitializeComponents();

    /**
     * @brief 验证配置
     * @return 是否有效
     */
    bool ValidateConfig() const;

    /**
     * @brief 检查依赖
     * @return 是否满足
     */
    bool CheckDependencies() const;

    /**
     * @brief 打印启动信息
     */
    void PrintStartupInfo() const;

    /**
     * @brief 打印统计信息
     */
    void PrintStats() const;

    /**
     * @brief 执行健康检查
     * @return 是否健康
     */
    bool HealthCheck() const;

    /**
     * @brief 处理退出
     * @param exit_code 退出码
     */
    void HandleExit(int exit_code);

    /**
     * @brief 清理资源
     */
    void Cleanup();

    /**
     * @brief 记录日志
     * @param level 日志级别
     * @param message 日志消息
     */
    void Log(const std::string& level, const std::string& message) const;

    /**
     * @brief 格式化运行时间
     * @return 运行时间字符串
     */
    std::string FormatUptime() const;

    /**
     * @brief 获取内存使用情况
     * @return 内存使用MB
     */
    double GetMemoryUsage() const;

    /**
     * @brief 获取CPU使用率
     * @return CPU使用率百分比
     */
    double GetCPUUsage() const;
}; 

#include <iostream>
#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <getopt.h>

#include "Application.h"

/**
 * @brief 显示使用帮助
 */
void ShowUsage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [OPTIONS]\n\n"
              << "C++ Parser for Financial Device Communication System\n\n"
              << "Options:\n"
              << "  -c, --config FILE     Configuration file path (default: parser_config.json)\n"
              << "  -d, --daemon          Run as daemon\n"
              << "  -t, --threads NUM     Number of worker threads (override config)\n"
              << "  -v, --verbose         Enable verbose logging\n"
              << "  -h, --help            Show this help message\n"
              << "  -V, --version         Show version information\n"
              << "  --create-config       Create default configuration file\n"
              << "  --test-config         Test configuration file\n"
              << "  --health-check        Perform health check and exit\n"
              << "  --stats               Show statistics and exit\n"
              << "\n"
              << "Examples:\n"
              << "  " << program_name << " -c /etc/parser.json\n"
              << "  " << program_name << " --threads 8 --verbose\n"
              << "  " << program_name << " --create-config\n"
              << "  " << program_name << " --daemon\n"
              << std::endl;
}

/**
 * @brief 主函数
 */
int main(int argc, char* argv[]) {
    std::string config_file = "parser_config.json";
    bool daemon_mode = false;
    bool verbose = false;
    bool create_config = false;
    bool test_config = false;
    bool health_check = false;
    bool show_stats = false;
    int thread_count = 0;

    // 长选项定义
    static struct option long_options[] = {
        {"config",        required_argument, 0, 'c'},
        {"daemon",        no_argument,       0, 'd'},
        {"threads",       required_argument, 0, 't'},
        {"verbose",       no_argument,       0, 'v'},
        {"help",          no_argument,       0, 'h'},
        {"version",       no_argument,       0, 'V'},
        {"create-config", no_argument,       0, '1'},
        {"test-config",   no_argument,       0, '2'},
        {"health-check",  no_argument,       0, '3'},
        {"stats",         no_argument,       0, '4'},
        {0, 0, 0, 0}
    };

    // 解析命令行参数
    int option_index = 0;
    int c;
    while ((c = getopt_long(argc, argv, "c:dt:vhV", long_options, &option_index)) != -1) {
        switch (c) {
            case 'c':
                config_file = optarg;
                break;
            case 'd':
                daemon_mode = true;
                break;
            case 't':
                thread_count = std::atoi(optarg);
                if (thread_count <= 0) {
                    std::cerr << "Invalid thread count: " << optarg << std::endl;
                    return 1;
                }
                break;
            case 'v':
                verbose = true;
                break;
            case 'h':
                ShowUsage(argv[0]);
                return 0;
            case 'V':
                Application::ShowVersion();
                return 0;
            case '1':
                create_config = true;
                break;
            case '2':
                test_config = true;
                break;
            case '3':
                health_check = true;
                break;
            case '4':
                show_stats = true;
                break;
            case '?':
            default:
                ShowUsage(argv[0]);
                return 1;
        }
    }

    // 处理特殊操作
    if (create_config) {
        if (Application::CreateDefaultConfig(config_file)) {
            std::cout << "Default configuration created: " << config_file << std::endl;
            return 0;
        } else {
            std::cerr << "Failed to create configuration file: " << config_file << std::endl;
            return 1;
        }
    }

    try {
        // 创建应用程序实例
        Application app;

        // 初始化应用程序
        if (!app.Initialize(config_file)) {
            std::cerr << "Failed to initialize application with config: " << config_file << std::endl;
            return 1;
        }

        // 覆盖线程数设置（如果指定了命令行参数）
        if (thread_count > 0) {
            app.OverrideThreadCount(thread_count);
        }

        // 处理测试配置
        if (test_config) {
            std::cout << "Configuration test passed: " << config_file << std::endl;
            return 0;
        }

        // 处理健康检查
        if (health_check) {
            auto status = app.GetStatus();
            std::cout << "Health Check Results:\n";
            for (const auto& [key, value] : status) {
                std::cout << "  " << key << ": " << value << "\n";
            }
            return 0;
        }

        // 处理统计信息
        if (show_stats) {
            auto stats = app.GetPerformanceStats();
            std::cout << "Performance Statistics:\n";
            for (const auto& [key, value] : stats) {
                std::cout << "  " << key << ": " << value << "\n";
            }
            return 0;
        }

        // 守护进程模式
        if (daemon_mode) {
            std::cout << "Starting in daemon mode..." << std::endl;
            // 这里可以添加守护进程化的代码
            // daemon(0, 0);
        }

        // 运行应用程序
        std::cout << "Starting C++ Parser..." << std::endl;
        int exit_code = app.Run();
        
        std::cout << "Application exited with code: " << exit_code << std::endl;
        return exit_code;

    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Unknown fatal error occurred" << std::endl;
        return 1;
    }
} 
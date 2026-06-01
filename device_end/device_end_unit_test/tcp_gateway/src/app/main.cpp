#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

#include "logic/Config.h"
#include "dpower/redis/Interfaces.h"
#include "logic/TCPServer.h"
#include "logic/SessionManager.h"
#include "logic/TCPSession.h"
#include "logic/MultiProtocolManager.h"
#include "logic/PacketReassembler.h"
#include "json.hpp" 
#include "logic/ThreadPool.h"
#include "dpower/net/Interfaces.h"
#include "dpower/utils/Base64.h"

using json = nlohmann::json;

// 创建一个全局的线程池实例，参数可以不填，默认使用CPU核心数
// 让它在程序启动时创建，在程序结束时自动销毁
ThreadPool g_thread_pool; 

// 后台线程函数
//如果项目的需求是尽可能降低响应延迟，并且不需要在后台线程中执行周期性任务，那么改用 BLPOP 会是更好的选择
void response_poller_thread(
    std::shared_ptr<DPower::Redis::DPowerRedisClient> redis_client,
    std::shared_ptr<SessionManager> session_manager,
    const std::string& response_queue_key
) {
    std::cout << "[INFO] Response poller thread started. Listening to Redis queue: '" << response_queue_key << "'" << std::endl;
    
    while (true) {
        try {
            auto result = redis_client->ListBlockingPop(response_queue_key, 5000); // 5秒超时

            if (result.success) {
                auto payload = json::parse(result.data);
                const std::string client_id = payload.at("client_id");
                const std::string response_b64 = payload.at("response_data_base64");
                
                std::cout << "[RESPONSE] Popped response for client: " << client_id << std::endl;

                std::vector<uint8_t> response_data;
                response_data.resize(DPower::Utils::DPowerBase64::DecodedSize(response_b64.size()));
                auto const decode_result = DPower::Utils::DPowerBase64::Decode(response_data.data(), response_b64.data(), response_b64.size());
                response_data.resize(decode_result.first);
                
                auto session = session_manager->find(client_id);
                
                if (session) {
		            session->write_response(std::make_shared<std::vector<uint8_t>>(response_data));
                } else {
                    std::cerr << "[WARN] Session not found for client: " << client_id << ". Response discarded." << std::endl;
                }
            }
        } catch (const std::exception& e) {
            std::cerr << "[ERROR] Exception in response poller thread: " << e.what() << std::endl;
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
}

// 分包重组器清理线程
void packet_reassembler_cleanup_thread(std::shared_ptr<PacketReassembler> packet_reassembler) {
    std::cout << "[INFO] Packet reassembler cleanup thread started" << std::endl;
    
    while (true) {
        try {
            std::this_thread::sleep_for(std::chrono::seconds(60)); // 每60秒清理一次
            
            size_t before_count = packet_reassembler->GetActiveSessionCount();
            packet_reassembler->CleanupExpiredSessions();
            size_t after_count = packet_reassembler->GetActiveSessionCount();
            
            if (before_count != after_count) {
                std::cout << "[CLEANUP] Packet reassembler sessions: " << before_count 
                          << " -> " << after_count << " (cleaned " << (before_count - after_count) << ")" << std::endl;
            }
            
            // 每10分钟打印一次统计信息
            static int cleanup_cycles = 0;
            if (++cleanup_cycles % 10 == 0) {
                auto stats = packet_reassembler->GetStatistics();
                std::cout << "[STATS] PacketReassembler Statistics:" << std::endl;
                for (const auto& [key, value] : stats) {
                    std::cout << "        " << key << ": " << value << std::endl;
                }
            }
            
        } catch (const std::exception& e) {
            std::cerr << "[ERROR] Exception in packet reassembler cleanup thread: " << e.what() << std::endl;
        }
    }
}

// 主函数
int main(int argc, char* argv[]) {
    try {
        const std::string config_path = "config/gateway.conf";
        std::cout << "[INFO] Loading configuration from: " << config_path << std::endl;
        AppConfig config = Config::load(config_path);

        auto netFactory = DPower::Net::CreateBoostNetFactory();
        auto io_context = netFactory->CreateIO();

        // 1. 为"写入"任务（被TCPSession使用）创建一个Redis客户端
        auto redis_writer_factory = DPower::Redis::CreateSwRedisFactory();
        auto redis_writer_client = redis_writer_factory->Create();
        auto writer_conn_result = redis_writer_client->Connect(config.redis_host, config.redis_port);
        if (!writer_conn_result.success) {
            throw std::runtime_error("Failed to connect writer Redis client: " + writer_conn_result.error_message);
        }

        // 2. 为"读取"任务（被轮询线程使用）创建另一个完全独立的Redis客户端
        auto redis_reader_factory = DPower::Redis::CreateSwRedisFactory();
        auto redis_reader_client = redis_reader_factory->Create();
        auto reader_conn_result = redis_reader_client->Connect(config.redis_host, config.redis_port);
        if (!reader_conn_result.success) {
            throw std::runtime_error("Failed to connect reader Redis client: " + reader_conn_result.error_message);
        }
        
        // 3. 创建多协议管理器
        auto protocol_manager = std::make_shared<MultiProtocolManager>();
        if (!protocol_manager->LoadProtocolConfig(config.protocol_registry_file)) {
            throw std::runtime_error("Failed to load protocol configuration from: " + config.protocol_registry_file);
        }
        
        // 4. 创建分包重组器
        auto packet_reassembler = std::make_shared<PacketReassembler>(30); // 30秒超时
        std::cout << "[INFO] Packet reassembler initialized with 30 seconds timeout" << std::endl;
        
        // 5. 将"写入"客户端传递给TCPServer，并传递端口配置和Stream键名
        auto session_manager = std::make_shared<SessionManager>();
        TCPServer server(*netFactory, *io_context, std::shared_ptr<DPower::Redis::DPowerRedisClient>(redis_writer_client.release()), session_manager, protocol_manager, packet_reassembler, config.redis_stream_key_request, config);

        // 6. 将"读取"客户端传递给后台线程（转换为shared_ptr）
        std::thread poller(response_poller_thread, std::shared_ptr<DPower::Redis::DPowerRedisClient>(redis_reader_client.release()), session_manager, config.redis_queue_name_response);
        poller.detach();
        
        // 7. 启动分包重组器清理线程
        std::thread cleanup_thread(packet_reassembler_cleanup_thread, packet_reassembler);
        cleanup_thread.detach();

        std::cout << "[INFO] TCP Gateway started successfully." << std::endl;
        std::cout << "        Redis Host: " << config.redis_host << ":" << config.redis_port << std::endl;
        std::cout << "        Request Stream: '" << config.redis_stream_key_request << "'" << std::endl;
        std::cout << "        Response Queue: '" << config.redis_queue_name_response << "'" << std::endl;
        std::cout << "        Protocol Registry: " << config.protocol_registry_file << std::endl;
        std::cout << "        Default Protocol: " << config.default_protocol << std::endl;
        
        // 显示端口-协议映射
        if (!config.listen_ports.empty()) {
            std::cout << "        Port-Protocol Mappings:" << std::endl;
            for (const auto& port_config : config.listen_ports) {
                std::cout << "          Port " << port_config.first << " -> " << port_config.second << std::endl;
            }
        } else {
            std::cout << "        Using protocol registry port mappings" << std::endl;
        }
        
        std::cout << "        Max Connections: " << config.max_connections << std::endl;
        std::cout << "        Worker Threads: " << (config.worker_threads == 0 ? "auto" : std::to_string(config.worker_threads)) << std::endl;
        std::cout << "--------------------------------------------------------" << std::endl;

        io_context->Run();

    } catch (const std::exception& e) {
        std::cerr << "[FATAL] An exception occurred: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}

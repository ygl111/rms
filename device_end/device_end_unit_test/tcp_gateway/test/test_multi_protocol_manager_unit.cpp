/**
 * @file test_multi_protocol_manager_unit.cpp
 * @brief 多协议管理器单元测试 - 第二优先级测试
 * @author AI Assistant
 * @date 2025-09-26
 * 
 * 测试重点：协议识别准确率、协议配置加载、协议切换逻辑
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <memory>
#include <fstream>

// 包含待测试的头文件
#include "logic/MultiProtocolManager.h"

class MultiProtocolManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        manager_ = std::make_unique<MultiProtocolManager>();
        CreateTestProtocolRegistry();
    }

    void TearDown() override {
        std::remove("test_protocol_registry.json");
    }

    void CreateTestProtocolRegistry() {
        std::ofstream registry_file("test_protocol_registry.json");
        registry_file << R"({
            "protocols": [
                {
                    "name": "dp_protocol_v1",
                    "version": "1.0",
                    "identification": {
                        "header_pattern": "5555",
                        "min_length": 34,
                        "max_length": 1024
                    },
                    "message_types": {
                        "1001": "heartbeat",
                        "1002": "login_request", 
                        "1003": "banknote_report",
                        "2001": "fault_report"
                    }
                },
                {
                    "name": "modbus_tcp",
                    "version": "1.0",
                    "identification": {
                        "header_pattern": "0000",
                        "min_length": 12,
                        "max_length": 260
                    },
                    "message_types": {
                        "0001": "read_coils",
                        "0003": "read_holding_registers"
                    }
                }
            ]
        })";
        registry_file.close();
    }

    std::unique_ptr<MultiProtocolManager> manager_;
};

// 🔥 核心测试：协议配置加载
TEST_F(MultiProtocolManagerTest, LoadProtocolConfiguration) {
    EXPECT_TRUE(manager_->LoadProtocolConfig("test_protocol_registry.json"));
    
    // 测试不存在的配置文件
    EXPECT_FALSE(manager_->LoadProtocolConfig("nonexistent_config.json"));
}

// 🔥 核心测试：协议识别准确率
TEST_F(MultiProtocolManagerTest, ProtocolIdentificationAccuracy) {
    manager_->LoadProtocolConfig("test_protocol_registry.json");
    
    // 测试DP协议v1识别
    std::vector<uint8_t> dp_v1_data = {
        0x55, 0x55,  // DP协议头部签名
        0x03, 0x00, 0x10, 0x00,
        0xE9, 0x03   // 更多数据...
    };
    
    std::string identified_protocol = manager_->IdentifyProtocol(dp_v1_data);
    EXPECT_EQ(identified_protocol, "dp_protocol_v1");
    
    // 测试Modbus TCP识别  
    std::vector<uint8_t> modbus_data = {
        0x00, 0x00,  // Modbus TCP头部
        0x00, 0x00, 0x00, 0x06,
        0x01, 0x03   // 功能码等...
    };
    
    identified_protocol = manager_->IdentifyProtocol(modbus_data);
    EXPECT_EQ(identified_protocol, "modbus_tcp");
}

// 🔥 边界测试：无效数据协议识别
TEST_F(MultiProtocolManagerTest, InvalidDataProtocolIdentification) {
    manager_->LoadProtocolConfig("test_protocol_registry.json");
    
    // 测试空数据
    std::vector<uint8_t> empty_data;
    std::string result1 = manager_->IdentifyProtocol(empty_data);
    EXPECT_EQ(result1, "unknown");
    
    // 测试数据太短
    std::vector<uint8_t> short_data = {0x55};
    std::string result2 = manager_->IdentifyProtocol(short_data);
    EXPECT_EQ(result2, "unknown");
    
    // 测试无法识别的头部
    std::vector<uint8_t> unknown_data = {0xFF, 0xFF, 0x00, 0x00};
    std::string result3 = manager_->IdentifyProtocol(unknown_data);
    EXPECT_EQ(result3, "unknown");
}

// 🔥 性能测试：协议列表获取
TEST_F(MultiProtocolManagerTest, GetSupportedProtocolsList) {
    manager_->LoadProtocolConfig("test_protocol_registry.json");
    
    auto protocols = manager_->GetSupportedProtocols();
    
    EXPECT_GE(protocols.size(), 2);
    EXPECT_TRUE(std::find(protocols.begin(), protocols.end(), "dp_protocol_v1") != protocols.end());
    EXPECT_TRUE(std::find(protocols.begin(), protocols.end(), "modbus_tcp") != protocols.end());
}

// 🔥 消息类型测试：特定协议的消息类型获取
TEST_F(MultiProtocolManagerTest, GetProtocolMessageTypes) {
    manager_->LoadProtocolConfig("test_protocol_registry.json");
    
    // 测试DP协议v1的消息类型
    auto dp_msg_types = manager_->GetProtocolMessageTypes("dp_protocol_v1");
    EXPECT_GE(dp_msg_types.size(), 4);
    
    // 验证特定消息类型存在
    EXPECT_TRUE(dp_msg_types.count("1001") > 0);  // heartbeat
    EXPECT_TRUE(dp_msg_types.count("1002") > 0);  // login_request
    EXPECT_TRUE(dp_msg_types.count("1003") > 0);  // banknote_report
    
    // 测试不存在的协议
    auto unknown_types = manager_->GetProtocolMessageTypes("unknown_protocol");
    EXPECT_EQ(unknown_types.size(), 0);
}

// 🔥 协议验证测试：协议有效性检查
TEST_F(MultiProtocolManagerTest, ProtocolValidation) {
    manager_->LoadProtocolConfig("test_protocol_registry.json");
    
    // 测试有效协议
    EXPECT_TRUE(manager_->IsProtocolSupported("dp_protocol_v1"));
    EXPECT_TRUE(manager_->IsProtocolSupported("modbus_tcp"));
    
    // 测试无效协议
    EXPECT_FALSE(manager_->IsProtocolSupported("unknown_protocol"));
    EXPECT_FALSE(manager_->IsProtocolSupported(""));
}

// 🔥 并发安全测试：多线程协议识别
TEST_F(MultiProtocolManagerTest, ConcurrentProtocolIdentification) {
    manager_->LoadProtocolConfig("test_protocol_registry.json");
    
    std::vector<std::thread> threads;
    std::vector<std::string> results(10);
    
    // 创建多个线程同时进行协议识别
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([this, i, &results]() {
            std::vector<uint8_t> test_data = {0x55, 0x55, 0x03, 0x00, 0x10, 0x00};
            results[i] = manager_->IdentifyProtocol(test_data);
        });
    }
    
    // 等待所有线程完成
    for (auto& thread : threads) {
        thread.join();
    }
    
    // 验证所有结果都正确
    for (const auto& result : results) {
        EXPECT_EQ(result, "dp_protocol_v1");
    }
}

// 主函数
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
/**
 * @file test_universal_parser_unit.cpp
 * @brief 通用解析器核心单元测试 - 最高优先级测试
 * @author AI Assistant
 * @date 2025-09-26
 * 
 * 测试重点：协议解析正确性、消息ID识别、字段提取准确性
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <memory>
#include <vector>
#include <string>
#include <fstream>

// 包含待测试的头文件
#include "logic/UniversalParser.h"

class UniversalParserTest : public ::testing::Test {
protected:
    void SetUp() override {
        parser_ = std::make_unique<UniversalParser>();
        
        // 创建测试用的协议配置文件
        CreateTestConfigFiles();
    }

    void TearDown() override {
        // 清理测试文件
        std::remove("test_rules.json");
        std::remove("test_strategies.json");
    }

    void CreateTestConfigFiles() {
        // 创建测试解析规则
        std::ofstream rules_file("test_rules.json");
        rules_file << R"({
            "parsing_rules": {
                "dp_protocol_v1": {
                    "header_signature": "5555",
                    "header_length": 2,
                    "message_id_offset": 6,
                    "message_id_length": 2,
                    "device_id_offset": 8,
                    "device_id_length": 24,
                    "data_start_offset": 32
                }
            }
        })";
        rules_file.close();

        // 创建测试协议策略
        std::ofstream strategies_file("test_strategies.json");
        strategies_file << R"({
            "strategies": {
                "dp_protocol_v1": {
                    "supported_message_types": [1001, 1002, 1003, 2001],
                    "parsing_strategy": "binary",
                    "byte_order": "little_endian"
                }
            }
        })";
        strategies_file.close();
    }

    std::unique_ptr<UniversalParser> parser_;
};

// 🔥 最关键测试：协议解析基础功能
TEST_F(UniversalParserTest, LoadConfigurationFiles) {
    // 测试配置文件加载
    EXPECT_TRUE(parser_->LoadParsingRules("test_rules.json"));
    EXPECT_TRUE(parser_->LoadProtocolStrategies("test_strategies.json"));
    
    // 测试不存在文件的处理
    EXPECT_FALSE(parser_->LoadParsingRules("nonexistent.json"));
    EXPECT_FALSE(parser_->LoadProtocolStrategies("nonexistent.json"));
}

// 🔥 最关键测试：消息ID识别准确性
TEST_F(UniversalParserTest, MessageIdExtraction) {
    parser_->LoadParsingRules("test_rules.json");
    parser_->LoadProtocolStrategies("test_strategies.json");
    
    // 测试数据：构造一个DP协议v1消息
    // Header: 0x5555, MsgType: 0x03, Length: 0x1000, MsgID: 0x03E9 (1001)
    std::vector<uint8_t> test_data = {
        0x55, 0x55,                     // Header signature
        0x03,                           // Message type  
        0x00, 0x10,                     // Length (little endian)
        0x00,                           // Reserved
        0xE9, 0x03,                     // Message ID 1001 (little endian)
        'T', 'E', 'S', 'T', '_', 'D', 'E', 'V', // Device ID starts
        '_', '0', '0', '1', 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x01, 0x02                      // Data payload
    };
    
    // Base64编码测试数据
    std::string base64_data = "VVUDAwAAAOkDVEVTVF9ERVZfMDAxAAAAAAAAAAAAAAAAAQI=";
    
    auto result = parser_->ParseMessage("dp_protocol_v1", base64_data, "192.168.1.100");
    
    EXPECT_TRUE(result.is_valid);
    EXPECT_EQ(result.msg_id, 1001);
    EXPECT_EQ(result.source_ip, "192.168.1.100");
    EXPECT_TRUE(result.extracted_fields.count("device_id") > 0);
}

// 🔥 最关键测试：字段提取准确性
TEST_F(UniversalParserTest, FieldExtractionAccuracy) {
    parser_->LoadParsingRules("test_rules.json");
    parser_->LoadProtocolStrategies("test_strategies.json");
    
    std::string base64_data = "VVUDAwAAAOkDVEVTVF9ERVZfMDAxAAAAAAAAAAAAAAAAAQI=";
    auto result = parser_->ParseMessage("dp_protocol_v1", base64_data, "192.168.1.100");
    
    EXPECT_TRUE(result.is_valid);
    
    // 验证设备ID提取
    EXPECT_TRUE(result.extracted_fields.count("device_id") > 0);
    std::string extracted_device_id = result.extracted_fields.at("device_id");
    EXPECT_EQ(extracted_device_id, "TEST_DEV_001");
}

// 🔥 异常处理测试：无效数据处理能力
TEST_F(UniversalParserTest, InvalidDataHandling) {
    parser_->LoadParsingRules("test_rules.json");
    parser_->LoadProtocolStrategies("test_strategies.json");
    
    // 测试空数据
    auto result1 = parser_->ParseMessage("dp_protocol_v1", "", "192.168.1.100");
    EXPECT_FALSE(result1.is_valid);
    
    // 测试无效Base64
    auto result2 = parser_->ParseMessage("dp_protocol_v1", "InvalidBase64!!!", "192.168.1.100");
    EXPECT_FALSE(result2.is_valid);
    
    // 测试数据太短
    auto result3 = parser_->ParseMessage("dp_protocol_v1", "VVU=", "192.168.1.100");
    EXPECT_FALSE(result3.is_valid);
    
    // 测试无效协议
    auto result4 = parser_->ParseMessage("unknown_protocol", "VVUDAwAAAOkD", "192.168.1.100");
    EXPECT_FALSE(result4.is_valid);
}

// 🔥 性能关键测试：多消息类型支持
TEST_F(UniversalParserTest, MultipleMessageTypeSupport) {
    parser_->LoadParsingRules("test_rules.json");
    parser_->LoadProtocolStrategies("test_strategies.json");
    
    auto supported_types = parser_->GetSupportedMessageTypes();
    
    // 验证支持的消息类型
    EXPECT_GT(supported_types.size(), 0);
    EXPECT_TRUE(std::find(supported_types.begin(), supported_types.end(), 1001) != supported_types.end());
    EXPECT_TRUE(std::find(supported_types.begin(), supported_types.end(), 1002) != supported_types.end());
    EXPECT_TRUE(std::find(supported_types.begin(), supported_types.end(), 2001) != supported_types.end());
}

// 🔥 边界条件测试：协议边界处理
TEST_F(UniversalParserTest, ProtocolBoundaryConditions) {
    parser_->LoadParsingRules("test_rules.json");
    parser_->LoadProtocolStrategies("test_strategies.json");
    
    // 测试最小有效消息
    std::vector<uint8_t> minimal_data(34, 0x00);  // 最小34字节
    minimal_data[0] = 0x55;  // Header
    minimal_data[1] = 0x55;
    minimal_data[6] = 0xE9;  // Msg ID 1001
    minimal_data[7] = 0x03;
    
    // 手动Base64编码（简化版）
    std::string minimal_base64 = "VVUAAAAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
    
    auto result = parser_->ParseMessage("dp_protocol_v1", minimal_base64, "127.0.0.1");
    EXPECT_TRUE(result.is_valid);
    EXPECT_EQ(result.msg_id, 1001);
}

// 主函数
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
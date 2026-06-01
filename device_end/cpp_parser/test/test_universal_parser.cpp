#include <iostream>
#include <memory>
#include "logic/UniversalParser.h"

int main() {
    std::cout << "Testing Universal Parser..." << std::endl;
    
    // 创建通用解析器
    auto parser = std::make_unique<UniversalParser>();
    
    // 加载解析规则
    if (!parser->LoadParsingRules("config/universal_parsing_rules.json")) {
        std::cerr << "Failed to load parsing rules" << std::endl;
        return 1;
    }
    
    // 加载协议策略
    if (!parser->LoadProtocolStrategies("config/protocol_parsing_strategies.json")) {
        std::cerr << "Failed to load protocol strategies" << std::endl;
        return 1;
    }
    
    // 获取支持的消息类型
    auto supported_types = parser->GetSupportedMessageTypes();
    std::cout << "Supported message types: ";
    for (auto msg_id : supported_types) {
        std::cout << msg_id << " ";
    }
    std::cout << std::endl;
    
    // 测试解析一个示例消息
    std::string test_protocol = "dp_protocol_v1";
    std::string test_data = "VVUDAwAAAAAAABAAAAAA"; // 示例Base64数据
    std::string test_ip = "192.168.1.100";
    
    auto result = parser->ParseMessage(test_protocol, test_data, test_ip);
    
    if (result.is_valid) {
        std::cout << "Successfully parsed message with ID: " << result.msg_id << std::endl;
        std::cout << "Source IP: " << result.source_ip << std::endl;
        std::cout << "Extracted fields: " << result.extracted_fields.size() << std::endl;
    } else {
        std::cout << "Failed to parse message: " << result.error_message << std::endl;
    }
    
    return 0;
} 
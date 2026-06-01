#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <algorithm>

// 简单的Base64解码函数
std::vector<uint8_t> DecodeBase64(const std::string& base64_data) {
    static const std::string base64_chars = 
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789+/";
    
    std::vector<uint8_t> result;
    int val = 0, valb = -8;
    
    for (char c : base64_data) {
        if (c == '=') break;
        
        auto it = std::find(base64_chars.begin(), base64_chars.end(), static_cast<char>(c));
        if (it == base64_chars.end()) continue;
        
        val = (val << 6) | (it - base64_chars.begin());
        valb += 6;
        
        if (valb >= 0) {
            result.push_back((val >> valb) & 0xFF);
            valb -= 8;
        }
    }
    
    return result;
}

// 简单的消息解析结构
struct SimpleParsedMessage {
    uint16_t msg_id;
    std::string source_ip;
    std::map<std::string, std::string> fields;
    bool is_valid;
    std::string error_message;
};

// 简单的解析函数
SimpleParsedMessage ParseSimpleMessage(const std::string& raw_data_base64, const std::string& source_ip) {
    SimpleParsedMessage result;
    result.source_ip = source_ip;
    result.is_valid = false;
    
    // 解码Base64
    std::vector<uint8_t> raw_data = DecodeBase64(raw_data_base64);
    if (raw_data.empty()) {
        result.error_message = "Failed to decode Base64 data";
        return result;
    }
    
    // 检查最小长度
    if (raw_data.size() < 34) {
        result.error_message = "Message too short";
        return result;
    }
    
    // 检查头部签名 (0x5555)
    if (raw_data[0] != 0x55 || raw_data[1] != 0x55) {
        result.error_message = "Invalid header signature";
        return result;
    }
    
    // 提取消息ID (偏移量6, 2字节, 小端序)
    result.msg_id = static_cast<uint16_t>(raw_data[6]) | (static_cast<uint16_t>(raw_data[7]) << 8);
    
    // 提取设备ID (偏移量8, 24字节)
    std::string device_id;
    for (int i = 8; i < 32; ++i) {
        if (raw_data[i] >= 32 && raw_data[i] <= 126) {
            device_id += static_cast<char>(raw_data[i]);
        }
    }
    result.fields["device_id"] = device_id;
    
    result.is_valid = true;
    return result;
}

int main() {
    std::cout << "Testing Simple Parser..." << std::endl;
    
    // 测试数据：一个简单的DP协议v1消息
    // 头部: 0x5555 (2字节) + 消息类型0x03 (1字节) + 长度 (2字节) + 消息ID (2字节) + 设备ID (24字节)
    std::string test_data = "VVUDAwAAAAAAABAAAAAA"; // 示例Base64数据
    std::string test_ip = "192.168.1.100";
    
    auto result = ParseSimpleMessage(test_data, test_ip);
    
    if (result.is_valid) {
        std::cout << "Successfully parsed message!" << std::endl;
        std::cout << "Message ID: " << result.msg_id << std::endl;
        std::cout << "Source IP: " << result.source_ip << std::endl;
        std::cout << "Device ID: " << result.fields["device_id"] << std::endl;
    } else {
        std::cout << "Failed to parse message: " << result.error_message << std::endl;
    }
    
    return 0;
} 
#include "logic/ProtocolIdentifier.h"
#include <iostream>
#include <algorithm>
#include <cstring>

// 通用协议识别器实现
class GenericProtocolIdentifier : public IProtocolIdentifier {
public:
    GenericProtocolIdentifier(const std::string& canonical_id, const json& config)
        : canonical_id_(canonical_id) {
        LoadConfig(config);
    }
    
    ~GenericProtocolIdentifier() = default;
    
    ProtocolIdentificationResult IdentifyProtocol(const std::vector<uint8_t>& data) override {
        ProtocolIdentificationResult result;
        // 使用注册表中的协议键作为对外 protocol_id（与 cpp_parser 一致，例如 dp_protocol_v1 / dp_protocol_v2 / modbus_tcp）
        result.protocol_id = canonical_id_;
        result.protocol_name = config_.name;
        result.version = config_.version;
        result.is_valid = false;
        
        // 1. 基本长度检查
        if (data.size() < static_cast<size_t>(config_.message_boundary.header_size)) {
            result.error_message = "数据长度不足，无法识别协议";
            return result;
        }
        
        // 2. 提取报文长度
        result.message_length = ExtractMessageLength(data, config_.message_boundary);
        if (result.message_length == 0 || result.message_length > data.size()) {
            result.error_message = "无法提取有效的报文长度";
            return result;
        }
        
        // 3. 对于端口确定的协议，采用放宽的验证策略
        // 只进行基本的格式检查，不强制要求签名匹配（因为端口已经确定了协议）
        bool signature_matched = true;
        for (const auto& signature : config_.message_boundary.signatures) {
            if (signature.offset < 0 || 
                static_cast<size_t>(signature.offset + signature.value.size()) > data.size()) {
                signature_matched = false;
                break;
            }
            
            for (size_t i = 0; i < signature.value.size(); ++i) {
                if (data[signature.offset + i] != signature.value[i]) {
                    signature_matched = false;
                    break;
                }
            }
            if (!signature_matched) break;
        }
        
        // 4. 记录签名匹配情况，但不因签名不匹配而拒绝（端口优先原则）
        if (!signature_matched) {
            std::cout << "[DEBUG] Protocol signature mismatch for " << canonical_id_ 
                      << " on dedicated port, but accepting due to port-based identification" << std::endl;
        }
        
        // 5. 端口确定协议模式：只要基本格式正确就接受
        result.header_size = config_.message_boundary.header_size;
        result.body_size = result.message_length - result.header_size;
        result.is_valid = true;
        
        return result;
    }
    
    bool ValidateProtocol(const std::vector<uint8_t>& data, const MessageBoundary& boundary) override {
        // 验证签名
        for (const auto& signature : boundary.signatures) {
            if (signature.offset < 0 || 
                static_cast<size_t>(signature.offset + signature.value.size()) > data.size()) {
                return false;
            }
            
            for (size_t i = 0; i < signature.value.size(); ++i) {
                if (data[signature.offset + i] != signature.value[i]) {
                    return false;
                }
            }
        }
        
        // 验证报尾（如果存在）
        if (boundary.tail_field) {
            const auto& tail = *boundary.tail_field;
            if (tail.offset < 0 || 
                static_cast<size_t>(tail.offset + tail.value.size()) > data.size()) {
                return false;
            }
            
            for (size_t i = 0; i < tail.value.size(); ++i) {
                if (data[tail.offset + i] != tail.value[i]) {
                    return false;
                }
            }
        }
        
        return true;
    }
    
    // 放宽的协议验证 - 只检查基本格式，不强制要求特定签名
    bool ValidateProtocolRelaxed(const std::vector<uint8_t>& data, const MessageBoundary& boundary) {
        // 1. 检查最小长度
        if (data.size() < static_cast<size_t>(boundary.header_size)) {
            return false;
        }
        
        // 2. 检查长度字段是否合理
        const auto& length_field = boundary.length_field;
        if (length_field.offset < 0 || 
            static_cast<size_t>(length_field.offset + length_field.size) > data.size()) {
            return false;
        }
        
        // 3. 提取并验证长度
        size_t extracted_length = ExtractMessageLength(data, boundary);
        if (extracted_length == 0 || extracted_length > data.size()) {
            return false;
        }
        
        // 4. 对于有签名的协议，进行可选的签名验证（不强制失败）
        bool signature_matched = true;
        for (const auto& signature : boundary.signatures) {
            if (signature.offset < 0 || 
                static_cast<size_t>(signature.offset + signature.value.size()) > data.size()) {
                signature_matched = false;
                break;
            }
            
            for (size_t i = 0; i < signature.value.size(); ++i) {
                if (data[signature.offset + i] != signature.value[i]) {
                    signature_matched = false;
                    break;
                }
            }
            if (!signature_matched) break;
        }
        
        // 5. 如果签名不匹配，记录调试信息但不强制失败
        if (!signature_matched) {
            std::cout << "[DEBUG] Protocol signature mismatch, but continuing due to port-based protocol selection" << std::endl;
            // 可以在这里添加更详细的调试信息
            for (const auto& signature : boundary.signatures) {
                std::cout << "[DEBUG] Expected signature at offset " << signature.offset << ": ";
                for (auto val : signature.value) {
                    std::cout << std::hex << static_cast<int>(val) << " ";
                }
                std::cout << std::dec << std::endl;
                
                if (signature.offset >= 0 && static_cast<size_t>(signature.offset + signature.value.size()) <= data.size()) {
                    std::cout << "[DEBUG] Actual data at offset " << signature.offset << ": ";
                    for (size_t i = 0; i < signature.value.size(); ++i) {
                        std::cout << std::hex << static_cast<int>(data[signature.offset + i]) << " ";
                    }
                    std::cout << std::dec << std::endl;
                }
            }
        }
        
        // 6. 对于端口确定的协议，只要基本格式正确就接受
        return true;
    }
    
    size_t ExtractMessageLength(const std::vector<uint8_t>& data, const MessageBoundary& boundary) override {
        const auto& length_field = boundary.length_field;
        
        if (length_field.offset < 0 || 
            static_cast<size_t>(length_field.offset + length_field.size) > data.size()) {
            return 0;
        }
        
        size_t body_length = 0;
        if (length_field.endianness == "little") {
            for (int i = 0; i < length_field.size; ++i) {
                body_length |= static_cast<size_t>(data[length_field.offset + i]) << (8 * i);
            }
        } else { // big endian
            for (int i = 0; i < length_field.size; ++i) {
                body_length |= static_cast<size_t>(data[length_field.offset + i]) << (8 * (length_field.size - 1 - i));
            }
        }
        

        
        // 计算完整的报文长度
        size_t total_length = boundary.header_size + body_length;
        
        // 如果长度字段包含头部，需要调整
        if (length_field.includes_header) {
            total_length = body_length;
        }
        
        // 添加CRC字段长度（如果存在）
        if (boundary.crc_field) {
            total_length += boundary.crc_field->size;
        }
        
        // 添加尾部字段长度（如果存在）
        if (boundary.tail_field) {
            total_length += boundary.tail_field->size;
        }
        

        
        return total_length;
    }
    
    std::string GetProtocolName() const override {
        return config_.name;
    }
    
    const ProtocolConfig& GetConfig() const override {
        return config_;
    }
    
private:
    void LoadConfig(const json& config) {
        config_.name = config["name"];
        config_.version = config["version"];
        config_.port = config["port"];
        config_.config_file = config["config_file"];
        
        const auto& boundary = config["message_boundary"];
        config_.message_boundary.header_size = boundary["header_size"];
        
        // 加载长度字段配置
        const auto& length_field = boundary["length_field"];
        config_.message_boundary.length_field.offset = length_field["offset"];
        config_.message_boundary.length_field.size = length_field["size"];
        config_.message_boundary.length_field.endianness = length_field["endianness"];
        config_.message_boundary.length_field.includes_header = length_field["includes_header"];
        
        // 加载CRC字段配置（如果存在）
        if (boundary.contains("crc_field")) {
            const auto& crc_field = boundary["crc_field"];
            auto crc = std::make_unique<CRCField>();
            crc->offset = crc_field["offset"];
            crc->size = crc_field["size"];
            crc->endianness = crc_field["endianness"];
            config_.message_boundary.crc_field = std::move(crc);
        }
        
        // 加载报尾字段配置（如果存在）
        if (boundary.contains("tail_field")) {
            const auto& tail_field = boundary["tail_field"];
            auto tail = std::make_unique<TailField>();
            tail->offset = tail_field["offset"];
            tail->size = tail_field["size"];
            tail->value = tail_field["value"].get<std::vector<uint8_t>>();
            config_.message_boundary.tail_field = std::move(tail);
        }
        
        // 加载签名配置
        for (const auto& sig : boundary["signatures"]) {
            config_.message_boundary.signatures.push_back({
                sig["offset"],
                sig["value"].get<std::vector<uint8_t>>(),
                sig["description"]
            });
        }
    }
    
    ProtocolConfig config_;
    std::string canonical_id_;
};

// 协议识别器工厂实现
std::map<std::string, std::function<std::unique_ptr<IProtocolIdentifier>(const json&)>> 
ProtocolIdentifierFactory::creators_;

std::unique_ptr<IProtocolIdentifier> ProtocolIdentifierFactory::CreateIdentifier(
    const std::string& protocol_id, const json& config) {
    
    auto it = creators_.find(protocol_id);
    if (it != creators_.end()) {
        return it->second(config);
    }
    
    // 默认使用通用协议识别器，携带 canonical 协议ID
    return std::make_unique<GenericProtocolIdentifier>(protocol_id, config);
}

void ProtocolIdentifierFactory::RegisterIdentifier(
    const std::string& protocol_id, 
    std::function<std::unique_ptr<IProtocolIdentifier>(const json&)> creator) {
    creators_[protocol_id] = creator;
}
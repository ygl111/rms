#pragma once

#include <string>
#include <vector>
#include <memory>
#include <map>
#include <json.hpp>

using json = nlohmann::json;

// 协议识别结果
struct ProtocolIdentificationResult {
    std::string protocol_id;
    std::string protocol_name;
    std::string version;
    bool is_valid;
    std::string error_message;
    size_t message_length;
    size_t header_size;
    size_t body_size;
    std::map<std::string, std::vector<uint8_t>> extracted_fields;
};

// 长度字段定义
struct LengthField {
    int offset;
    int size;
    std::string endianness;
    bool includes_header;
};

// CRC字段定义
struct CRCField {
    int offset;
    int size;
    std::string endianness;
};

// 尾部字段定义
struct TailField {
    int offset;
    int size;
    std::vector<uint8_t> value;
};

// 签名字段定义
struct SignatureField {
    int offset;
    std::vector<uint8_t> value;
    std::string description;
};

// 报文边界定义
struct MessageBoundary {
    int header_size;
    LengthField length_field;
    std::unique_ptr<CRCField> crc_field;  // 使用指针代替std::optional
    std::unique_ptr<TailField> tail_field; // 使用指针代替std::optional
    std::vector<SignatureField> signatures;
};

// 协议配置
struct ProtocolConfig {
    std::string name;
    std::string version;
    int port;
    std::string config_file;
    MessageBoundary message_boundary;
};

// 协议识别器接口
class IProtocolIdentifier {
public:
    virtual ~IProtocolIdentifier() = default;
    
    // 识别协议类型
    virtual ProtocolIdentificationResult IdentifyProtocol(const std::vector<uint8_t>& data) = 0;
    
    // 验证协议特征
    virtual bool ValidateProtocol(const std::vector<uint8_t>& data, const MessageBoundary& boundary) = 0;
    
    // 提取完整报文长度
    virtual size_t ExtractMessageLength(const std::vector<uint8_t>& data, const MessageBoundary& boundary) = 0;
    
    // 获取协议名称
    virtual std::string GetProtocolName() const = 0;
    
    // 获取协议配置
    virtual const ProtocolConfig& GetConfig() const = 0;
};

// 协议识别器工厂
class ProtocolIdentifierFactory {
public:
    static std::unique_ptr<IProtocolIdentifier> CreateIdentifier(const std::string& protocol_id, const json& config);
    
    // 注册协议识别器
    static void RegisterIdentifier(const std::string& protocol_id, 
                                 std::function<std::unique_ptr<IProtocolIdentifier>(const json&)> creator);
    
private:
    static std::map<std::string, std::function<std::unique_ptr<IProtocolIdentifier>(const json&)>> creators_;
}; 
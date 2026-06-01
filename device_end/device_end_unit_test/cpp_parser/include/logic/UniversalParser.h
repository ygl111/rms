#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <cstdint>
#include <json.hpp>
#include <variant>
#include <optional>

using json = nlohmann::json;

/**
 * @brief 点钞信息中的 "各币种统计数据表"
 */
struct CountInfo {
    std::string currency_symbol; // 币种符号
    uint32_t denomination;       // 单张面值 (单位：分)
    uint16_t count;              // 张数
    uint32_t amount;             // 金额 (单位：分)
};

/**
 * @brief 点钞信息中的 "钞票数据表"
 */
struct NoteInfo {
    std::string currency_symbol; // 币种符号
    uint32_t denomination;       // 钞票面值 (单位：分)
    uint8_t note_version;        // 钞票版本
    uint8_t error_type;          // 报错类型
    uint16_t error_code;         // 报错代码
    std::string serial_number;   // 钞票序列号
};

/**
 * @brief 字段值类型
 */
using FieldValue = std::variant<std::string, uint8_t, uint16_t, uint32_t, std::vector<uint8_t>, std::vector<CountInfo>, std::vector<NoteInfo>>;

/**
 * @brief 通用解析后的消息数据
 */
struct UniversalParsedMessage {
    uint16_t msg_id;
    std::string source_ip;
    std::string raw_data_base64;
    std::map<std::string, FieldValue> extracted_fields;
    bool is_valid;
    std::string error_message;
    std::string protocol_id;  // 协议ID，用于确定响应格式
    
    // 辅助方法：获取字段值
    template<typename T>
    T GetField(const std::string& field_name, const T& default_value = T{}) const {
        auto it = extracted_fields.find(field_name);
        if (it != extracted_fields.end() && std::holds_alternative<T>(it->second)) {
            return std::get<T>(it->second);
        }
        return default_value;
    }
    
    // 检查字段是否存在
    bool HasField(const std::string& field_name) const {
        return extracted_fields.find(field_name) != extracted_fields.end();
    }
};

/**
 * @brief 字段结构定义
 */
struct FieldStructure {
    std::string name;            // 字段名
    int size;                    // 字段大小
    std::string type;            // 字段类型
    std::string endianness;      // 字节序
};

/**
 * @brief 复合字段类型定义
 */
struct CompositeFieldType {
    std::string name;            // 字段类型名
    std::string description;     // 描述
    std::vector<FieldStructure> structure; // 字段结构
};

/**
 * @brief 变长字段大小引用配置
 */
struct SizeRefConfig {
    std::string field_name;      // 引用字段名
    int offset;                  // 引用字段偏移量
    int size;                    // 引用字段大小
    std::string data_type;       // 引用字段数据类型
    int record_size;             // 每个记录的大小
};

/**
 * @brief 字段提取规则
 */
struct FieldExtractionRule {
    std::string field_name;      // 业务字段名
    std::string source_path;     // 源路径，如 "header.devUniqueId" 或 "body.deviceModel"
    std::string data_type;       // 数据类型
    int offset;                  // 字节偏移量（可以是固定值或特殊值"dynamic"）
    int size;                    // 字段大小
    std::string endianness;      // 字节序 ("little" 或 "big")
    bool required;               // 是否必需
    FieldValue default_value;    // 默认值
    std::string size_ref;        // 变长字段的长度引用
    std::string offset_ref;      // 动态偏移量的引用字段（当offset为"dynamic"时使用）
    std::string discriminator;   // 用于区分消息类型的字段
    std::optional<SizeRefConfig> size_ref_config; // 变长字段大小引用配置
    // 新增：通过协议schema推导偏移量/长度
    std::string schema_ref;      // schema中的字段名（如 dp_protocol_v1.messages.bodies[msg_id] 里的 name）
};

/**
 * @brief 消息解析规则
 */
struct MessageParsingRule {
    uint16_t msg_id;
    std::string name;
    std::string table_name;
    std::vector<FieldExtractionRule> fields;
    std::string protocol_id;     // 协议标识，用于确定解析策略
};

/**
 * @brief 协议解析策略
 */
struct ProtocolParsingStrategy {
    std::string protocol_id;
    int header_size;             // 头部大小
    std::string msg_id_field;    // 消息ID字段位置
    int msg_id_offset;           // 消息ID偏移量
    int msg_id_size;             // 消息ID大小
    std::string msg_id_endianness; // 消息ID字节序
    std::string length_field;    // 长度字段位置
    int length_offset;           // 长度偏移量
    int length_size;             // 长度大小
    std::string length_endianness; // 长度字节序
    bool length_includes_header; // 长度是否包含头部
    std::vector<uint8_t> header_signature; // 头部签名
    int header_signature_offset; // 头部签名偏移量
    std::vector<uint8_t> tail_signature;   // 尾部签名
    int tail_signature_offset;   // 尾部签名偏移量
    bool has_crc;                // 是否有CRC校验
    int crc_offset;              // CRC偏移量
    int crc_size;                // CRC大小
    std::string crc_endianness;  // CRC字节序
};

/**
 * @brief 通用解析器接口
 */
class IUniversalParser {
public:
    virtual ~IUniversalParser() = default;
    
    /**
     * @brief 加载解析规则配置
     */
    virtual bool LoadParsingRules(const std::string& rules_file) = 0;
    
    /**
     * @brief 加载协议解析策略
     */
    virtual bool LoadProtocolStrategies(const std::string& strategies_file) = 0;

    /**
     * @brief 启用/禁用schema推导
     */
    virtual void EnableSchemaResolver(bool enabled) = 0;

    /**
     * @brief 加载协议schema（从文件）
     */
    virtual bool LoadProtocolSchema(const std::string& protocol_id, const std::string& schema_file) = 0;
    /**
     * @brief 加载协议schema（直接传入JSON）
     */
    virtual bool LoadProtocolSchemaJson(const std::string& protocol_id, const json& schema) = 0;
    
    /**
     * @brief 解析消息
     */
    virtual UniversalParsedMessage ParseMessage(const std::string& protocol_id, 
                                               const std::string& raw_data_base64, 
                                               const std::string& source_ip) = 0;
    
    /**
     * @brief 获取支持的消息类型
     */
    virtual std::vector<uint16_t> GetSupportedMessageTypes() const = 0;
    
    /**
     * @brief 获取消息解析规则
     */
    virtual std::optional<MessageParsingRule> GetMessageRule(uint16_t msg_id) const = 0;
    
    /**
     * @brief 获取所有消息解析规则（用于获取消息类型名称）
     */
    virtual json GetMessageRules() const = 0;
    
    /**
     * @brief 获取协议解析策略
     */
    virtual std::optional<ProtocolParsingStrategy> GetProtocolStrategy(const std::string& protocol_id) const = 0;
    
    /**
     * @brief Base64编码
     */
    virtual std::string Base64Encode(const std::vector<uint8_t>& data) const = 0;
    
    /**
     * @brief Base64解码
     */
    virtual std::vector<uint8_t> DecodeBase64(const std::string& base64_data) const = 0;
    
    /**
     * @brief CRC校验
     */
    virtual bool ValidateCRC(const uint8_t* data, size_t size) const = 0;
    
    /**
     * @brief 计算CRC16
     */
    virtual uint16_t CalculateCRC16(const uint8_t* data, size_t size) const = 0;
};

/**
 * @brief 通用解析器实现
 */
class UniversalParser : public IUniversalParser {
public:
    UniversalParser();
    ~UniversalParser() override = default;
    
    bool LoadParsingRules(const std::string& rules_file) override;
    bool LoadProtocolStrategies(const std::string& strategies_file) override;
    // 新增：实现接口以启用schema推导与加载schema
    void EnableSchemaResolver(bool enabled) override;
    bool LoadProtocolSchema(const std::string& protocol_id, const std::string& schema_file) override;
    bool LoadProtocolSchemaJson(const std::string& protocol_id, const json& schema) override;
    UniversalParsedMessage ParseMessage(const std::string& protocol_id, 
                                       const std::string& raw_data_base64, 
                                       const std::string& source_ip) override;
    std::vector<uint16_t> GetSupportedMessageTypes() const override;
    std::optional<MessageParsingRule> GetMessageRule(uint16_t msg_id) const override;
    json GetMessageRules() const override;
    std::optional<ProtocolParsingStrategy> GetProtocolStrategy(const std::string& protocol_id) const override;
    std::string Base64Encode(const std::vector<uint8_t>& data) const override;
    std::vector<uint8_t> DecodeBase64(const std::string& base64_data) const override;
    bool ValidateCRC(const uint8_t* data, size_t size) const override;
    uint16_t CalculateCRC16(const uint8_t* data, size_t size) const override;

private:
    std::map<uint16_t, MessageParsingRule> message_rules_;
    std::map<std::string, ProtocolParsingStrategy> protocol_strategies_;
    std::map<std::string, CompositeFieldType> composite_field_types_; // 复合字段类型定义
    mutable std::vector<uint16_t> crc_table_;

    // schema解析相关
    bool schema_resolver_enabled_ = false; // 是否启用schema推导
    std::map<std::string, json> protocol_schemas_; // 协议ID -> 协议schema JSON
    
    /**
     * @brief 验证消息格式
     */
    bool ValidateMessageFormat(const std::vector<uint8_t>& raw_data, const ProtocolParsingStrategy& strategy) const;
    
    /**
     * @brief 提取消息ID
     */
    uint16_t ExtractMessageId(const std::vector<uint8_t>& raw_data, const ProtocolParsingStrategy& strategy) const;
    
    /**
     * @brief 提取字段值
     */
    std::optional<FieldValue> ExtractFieldValue(const std::vector<uint8_t>& raw_data, 
                                               const FieldExtractionRule& rule,
                                               const ProtocolParsingStrategy& strategy,
                                               const std::map<std::string, FieldValue>& extracted_fields,
                                               const MessageParsingRule& current_message_rule) const;
    
    /**
     * @brief 转换字段值类型
     */
    std::optional<FieldValue> ParseFieldValue(const std::vector<uint8_t>& raw_data,
                                             const std::string& data_type,
                                             const std::string& endianness,
                                             const std::string& field_name) const;
    
    /**
     * @brief 处理特殊字段（如点钞数据的数组）
     */
    std::optional<FieldValue> HandleSpecialFields(const std::string& field_name, 
                                                 const std::vector<uint8_t>& raw_data,
                                                 const MessageParsingRule& rule,
                                                 const ProtocolParsingStrategy& strategy) const;
    
    /**
     * @brief 解析字段路径
     */
    std::pair<std::string, std::string> ParseFieldPath(const std::string& source_path) const;
    
    /**
     * @brief 计算变长字段大小
     */
    size_t CalculateVariableFieldSize(const std::string& size_ref, 
                                     const std::vector<uint8_t>& raw_data,
                                     const ProtocolParsingStrategy& strategy) const;
    
    /**
     * @brief 获取变长字符串字段的长度
     */
    size_t GetVariableStringLength(const std::string& size_ref, 
                                  const std::map<std::string, FieldValue>& extracted_fields,
                                  const ProtocolParsingStrategy& strategy) const;
    
    /**
     * @brief 计算动态偏移量
     */
    int CalculateFieldEndOffset(const std::string& field_name_to_find_end_of,
                               const std::map<std::string, FieldValue>& extracted_fields,
                               const MessageParsingRule& current_message_rule) const;
    
    /**
     * @brief 初始化CRC表
     */
    void InitializeCRCTable();
    
    /**
     * @brief 解析币种统计数据
     */
    std::optional<FieldValue> ParseCurrencyStatistics(const std::vector<uint8_t>& raw_data, 
                                                     const std::string& endianness = "little") const;
    
    /**
     * @brief 解析钞票明细数据
     */
    std::optional<FieldValue> ParseNoteDetails(const std::vector<uint8_t>& raw_data, 
                                              const std::string& endianness = "little") const;
    
    /**
     * @brief 解析复合字段（使用配置驱动的解析）
     */
    std::optional<FieldValue> ParseCompositeField(const std::vector<uint8_t>& raw_data,
                                                 const std::string& field_type,
                                                 const std::string& endianness = "little") const;

    /**
     * @brief 基于协议schema解析，推导字段的实际offset与size
     * @param protocol_id 协议ID（如 dp_protocol_v1）
     * @param msg_id 消息ID
     * @param schema_field_name schema中的字段名
     * @param raw_data 原始报文字节
     * @param strategy 协议解析策略（用于获取header_size等）
     * @return pair<offset,size>；若失败，offset返回-1
     */
    std::pair<int, size_t> ResolveFieldOffsetAndSizeFromSchema(const std::string& protocol_id,
                                                               uint16_t msg_id,
                                                               const std::string& schema_field_name,
                                                               const std::vector<uint8_t>& raw_data,
                                                               const ProtocolParsingStrategy& strategy) const;
};
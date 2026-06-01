#include "logic/UniversalParser.h"
#include "logic/utils/MessageUtils.h"
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cstring>
#include <iostream>
#include <limits>

UniversalParser::UniversalParser() {
    InitializeCRCTable();
}

void UniversalParser::EnableSchemaResolver(bool enabled) {
    schema_resolver_enabled_ = enabled;
}

bool UniversalParser::LoadProtocolSchemaJson(const std::string& protocol_id, const json& schema) {
    try {
        protocol_schemas_[protocol_id] = schema;
        return true;
    } catch (...) {
        return false;
    }
}

bool UniversalParser::LoadProtocolSchema(const std::string& protocol_id, const std::string& schema_file) {
    try {
        std::ifstream f(schema_file);
        if (!f.is_open()) return false;
        json j; f >> j;
        protocol_schemas_[protocol_id] = j;
        return true;
    } catch (...) {
        return false;
    }
}

bool UniversalParser::LoadParsingRules(const std::string& rules_file) {
    try {
        std::ifstream file(rules_file);
        if (!file.is_open()) {
            return false;
        }
        
        json config;
        file >> config;
        
        // 加载消息解析规则
        if (config.contains("message_rules")) {
            auto rules = config["message_rules"];
            for (auto it = rules.begin(); it != rules.end(); ++it) {
                uint16_t msg_id = std::stoi(it.key());
                auto rule_data = it.value();
                
                MessageParsingRule rule;
                rule.msg_id = msg_id;
                rule.name = rule_data.value("name", "");
                rule.table_name = rule_data.value("table_name", "");
                rule.protocol_id = rule_data.value("protocol_id", "");
                
                auto fields = rule_data["fields"];
                for (const auto& field_data : fields) {
                    FieldExtractionRule field_rule;
                    field_rule.field_name = field_data.value("field_name", "");
                    field_rule.source_path = field_data.value("source_path", "");
                    field_rule.data_type = field_data.value("data_type", "");
                    
                    // 处理偏移量：支持固定值或"dynamic"
                    if (field_data.contains("offset")) {
                        auto offset_json = field_data["offset"];
                        if (offset_json.is_string() && offset_json.get<std::string>() == "dynamic") {
                            field_rule.offset = -1; // 使用-1表示动态偏移量
                        } else if (offset_json.is_number()) {
                            field_rule.offset = offset_json.get<int>();
                        } else {
                            field_rule.offset = 0; // 默认值
                        }
                    } else {
                        field_rule.offset = 0; // 默认值
                    }
                    
                    field_rule.size = field_data.value("size", 0);
                    field_rule.endianness = field_data.value("endianness", "little");
                    field_rule.required = field_data.value("required", false);
                    
                    // 处理默认值
                    if (field_data.contains("default")) {
                        auto default_val = field_data["default"];
                        if (default_val.is_null()) {
                            field_rule.default_value = std::string("");
                        } else if (default_val.is_string()) {
                            field_rule.default_value = default_val.get<std::string>();
                        } else if (default_val.is_number()) {
                            if (field_rule.data_type == "uint8") {
                                field_rule.default_value = static_cast<uint8_t>(default_val.get<int>());
                            } else if (field_rule.data_type == "uint16") {
                                field_rule.default_value = static_cast<uint16_t>(default_val.get<int>());
                            } else if (field_rule.data_type == "uint32") {
                                field_rule.default_value = static_cast<uint32_t>(default_val.get<int>());
                            } else if (field_rule.data_type == "uint64") {
                                field_rule.default_value = static_cast<uint64_t>(default_val.get<unsigned long long>());
                            }
                        }
                    }
                    
                    if (field_data.contains("size_ref")) {
                        field_rule.size_ref = field_data.value("size_ref", "");
                    }
                    
                    if (field_data.contains("offset_ref")) {
                        field_rule.offset_ref = field_data.value("offset_ref", "");
                    }
                    
                    if (field_data.contains("size_ref_config")) {
                        auto size_ref_config_data = field_data["size_ref_config"];
                        SizeRefConfig size_ref_config;
                        size_ref_config.field_name = size_ref_config_data.value("field_name", "");
                        size_ref_config.offset = size_ref_config_data.value("offset", 0);
                        size_ref_config.size = size_ref_config_data.value("size", 0);
                        size_ref_config.data_type = size_ref_config_data.value("data_type", "");
                        size_ref_config.record_size = size_ref_config_data.value("record_size", 0);
                        field_rule.size_ref_config = size_ref_config;
                    }
                    
                    if (field_data.contains("discriminator")) {
                        field_rule.discriminator = field_data.value("discriminator", "");
                    }

                    if (field_data.contains("schema_ref")) {
                        field_rule.schema_ref = field_data.value("schema_ref", "");
                    }
                    
                    rule.fields.push_back(field_rule);
                }
                
                message_rules_[msg_id] = rule;
            }
        }
        
        // 加载复合字段类型定义
        if (config.contains("field_types")) {
            auto field_types = config["field_types"];
            for (auto it = field_types.begin(); it != field_types.end(); ++it) {
                std::string type_name = it.key();
                auto type_data = it.value();
                
                // 只处理有结构定义的复合字段类型
                if (type_data.contains("structure") && type_data["structure"].is_array()) {
                    CompositeFieldType composite_type;
                    composite_type.name = type_name;
                    composite_type.description = type_data.value("description", "");
                    
                    auto structure = type_data["structure"];
                    for (const auto& field_data : structure) {
                        FieldStructure field_struct;
                        field_struct.name = field_data.value("name", "");
                        field_struct.size = field_data.value("size", 0);
                        field_struct.type = field_data.value("type", "");
                        field_struct.endianness = field_data.value("endianness", "little");
                        field_struct.size_ref = field_data.value("size_ref", "");
                        composite_type.structure.push_back(field_struct);
                    }
                    
                    composite_field_types_[type_name] = composite_type;
                }
            }
        }
        
        return true;
    } catch (const std::exception& e) {
        return false;
    }
}

bool UniversalParser::LoadProtocolStrategies(const std::string& strategies_file) {
    try {
        std::ifstream file(strategies_file);
        if (!file.is_open()) {
            return false;
        }
        
        json config;
        file >> config;
        
        // 加载协议解析策略
        if (config.contains("protocol_strategies")) {
            auto strategies = config["protocol_strategies"];
            for (auto it = strategies.begin(); it != strategies.end(); ++it) {
                std::string protocol_id = it.key();
                auto strategy_data = it.value();
                
                ProtocolParsingStrategy strategy;
                strategy.protocol_id = protocol_id;
                strategy.header_size = strategy_data.value("header_size", 0);
                strategy.msg_id_field = strategy_data.value("msg_id_field", "");
                strategy.msg_id_offset = strategy_data.value("msg_id_offset", 0);
                strategy.msg_id_size = strategy_data.value("msg_id_size", 0);
                strategy.msg_id_endianness = strategy_data.value("msg_id_endianness", "little");
                strategy.length_field = strategy_data.value("length_field", "");
                strategy.length_offset = strategy_data.value("length_offset", 0);
                strategy.length_size = strategy_data.value("length_size", 0);
                strategy.length_endianness = strategy_data.value("length_endianness", "little");
                strategy.length_includes_header = strategy_data.value("length_includes_header", false);
                
                if (strategy_data.contains("header_signature")) {
                    strategy.header_signature = strategy_data["header_signature"].get<std::vector<uint8_t>>();
                    strategy.header_signature_offset = strategy_data.value("header_signature_offset", 0);
                }
                
                if (strategy_data.contains("tail_signature")) {
                    strategy.tail_signature = strategy_data["tail_signature"].get<std::vector<uint8_t>>();
                    strategy.tail_signature_offset = strategy_data.value("tail_signature_offset", 0);
                }
                
                if (strategy_data.contains("has_crc")) {
                    strategy.has_crc = strategy_data.value("has_crc", false);
                    if (strategy.has_crc) {
                        strategy.crc_offset = strategy_data.value("crc_offset", 0);
                        strategy.crc_size = strategy_data.value("crc_size", 0);
                        strategy.crc_endianness = strategy_data.value("crc_endianness", "little");
                    }
                }
                
                protocol_strategies_[protocol_id] = strategy;
            }
        }
        
        return true;
    } catch (const std::exception& e) {
        return false;
    }
}

UniversalParsedMessage UniversalParser::ParseMessage(const std::string& protocol_id, 
                                                   const std::string& raw_data_base64, 
                                                   const std::string& source_ip) {
    UniversalParsedMessage result;
    result.source_ip = source_ip;
    result.raw_data_base64 = raw_data_base64;
    result.is_valid = false;
    result.protocol_id = protocol_id;  // 设置协议ID
    
    // 获取协议解析策略
    auto strategy_it = protocol_strategies_.find(protocol_id);
    if (strategy_it == protocol_strategies_.end()) {
        result.error_message = "Unsupported protocol: " + protocol_id;
        return result;
    }
    
    const auto& strategy = strategy_it->second;
    
    // 解码原始数据
    std::vector<uint8_t> raw_data = DecodeBase64(raw_data_base64);
    if (raw_data.empty()) {
        result.error_message = "Failed to decode Base64 data";
        return result;
    }
    

    
    // 验证消息格式
    if (!ValidateMessageFormat(raw_data, strategy)) {
        result.error_message = "Invalid message format";
        return result;
    }
    
    // 提取消息ID
    result.msg_id = ExtractMessageId(raw_data, strategy);
    
    // 查找消息解析规则
    auto rule_it = message_rules_.find(result.msg_id);
    if (rule_it == message_rules_.end()) {
        result.error_message = "Unsupported message type: " + std::to_string(result.msg_id);
        return result;
    }
    
    const auto& rule = rule_it->second;
    
    // 提取字段（按顺序解析，支持动态偏移量）
    for (const auto& field_rule : rule.fields) {
        auto field_value = ExtractFieldValue(raw_data, field_rule, strategy, result.extracted_fields, rule);
        
        if (field_value.has_value()) {
            result.extracted_fields[field_rule.field_name] = *field_value;
        } else if (field_rule.required) {
            result.error_message = "Missing required field: " + field_rule.field_name;
            return result;
        } else {
            // 使用默认值
            result.extracted_fields[field_rule.field_name] = field_rule.default_value;
        }
    }
    
    result.is_valid = true;
    return result;
}

std::vector<uint16_t> UniversalParser::GetSupportedMessageTypes() const {
    std::vector<uint16_t> types;
    for (const auto& [msg_id, _] : message_rules_) {
        types.push_back(msg_id);
    }
    return types;
}

std::optional<MessageParsingRule> UniversalParser::GetMessageRule(uint16_t msg_id) const {
    auto it = message_rules_.find(msg_id);
    if (it != message_rules_.end()) {
        return it->second;
    }
    return std::nullopt;
}

json UniversalParser::GetMessageRules() const {
    json result;
    
    // 将内存中的消息规则转换为JSON格式
    for (const auto& pair : message_rules_) {
        uint16_t msg_id = pair.first;
        const MessageParsingRule& rule = pair.second;
        
        json rule_json;
        rule_json["name"] = rule.name;
        rule_json["table_name"] = rule.table_name;
        rule_json["protocol_id"] = rule.protocol_id;
        
        result[std::to_string(msg_id)] = rule_json;
    }
    
    return result;
}

std::optional<ProtocolParsingStrategy> UniversalParser::GetProtocolStrategy(const std::string& protocol_id) const {
    auto it = protocol_strategies_.find(protocol_id);
    if (it != protocol_strategies_.end()) {
        return it->second;
    }
    return std::nullopt;
}

std::vector<uint8_t> UniversalParser::DecodeBase64(const std::string& base64_data) const {
    // 简单的Base64解码实现
    static const std::string base64_chars = 
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789+/";
    
    std::vector<uint8_t> result;
    int val = 0, valb = -8;
    
    for (char c : base64_data) {
        if (c == '=') break;
        
        auto it = std::find(base64_chars.begin(), base64_chars.end(), c);
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

bool UniversalParser::ValidateMessageFormat(const std::vector<uint8_t>& raw_data, const ProtocolParsingStrategy& strategy) const {
    // 检查最小长度
    if (raw_data.size() < static_cast<size_t>(strategy.header_size)) {
        return false;
    }
    
    // 检查头部签名
    if (!strategy.header_signature.empty()) {
        if (strategy.header_signature_offset + strategy.header_signature.size() > raw_data.size()) {
            return false;
        }
        
        for (size_t i = 0; i < strategy.header_signature.size(); ++i) {
            if (raw_data[strategy.header_signature_offset + i] != strategy.header_signature[i]) {
                return false;
            }
        }
    }
    
    // 检查尾部签名
    if (!strategy.tail_signature.empty()) {
        if (strategy.tail_signature_offset + strategy.tail_signature.size() > raw_data.size()) {
            return false;
        }
        
        for (size_t i = 0; i < strategy.tail_signature.size(); ++i) {
            if (raw_data[raw_data.size() - strategy.tail_signature.size() + i] != strategy.tail_signature[i]) {
                return false;
            }
        }
    }
    
    return true;
}

uint16_t UniversalParser::ExtractMessageId(const std::vector<uint8_t>& raw_data, const ProtocolParsingStrategy& strategy) const {
    if (static_cast<size_t>(strategy.msg_id_offset + strategy.msg_id_size) > raw_data.size()) {
        return 0;
    }
    
    uint16_t msg_id = 0;
    if (strategy.msg_id_endianness == "little") {
        for (int i = 0; i < strategy.msg_id_size; ++i) {
            msg_id |= (static_cast<uint16_t>(raw_data[strategy.msg_id_offset + i]) << (i * 8));
        }
    } else { // big endian
        for (int i = 0; i < strategy.msg_id_size; ++i) {
            msg_id |= (static_cast<uint16_t>(raw_data[strategy.msg_id_offset + i]) << ((strategy.msg_id_size - 1 - i) * 8));
        }
    }
    
    return msg_id;
}

std::optional<FieldValue> UniversalParser::ExtractFieldValue(const std::vector<uint8_t>& raw_data, 
                                                           const FieldExtractionRule& rule,
                                                           const ProtocolParsingStrategy& strategy,
                                                           const std::map<std::string, FieldValue>& extracted_fields,
                                                           const MessageParsingRule& current_message_rule) const {
    // 计算实际偏移量
    int actual_offset = rule.offset;
    size_t field_size = rule.size;

    // 如果开启了schema推导且配置了schema_ref，则优先尝试从schema推导
    if (schema_resolver_enabled_ && !rule.schema_ref.empty()) {
        auto resolved = ResolveFieldOffsetAndSizeFromSchema(current_message_rule.protocol_id.empty() ? strategy.protocol_id : current_message_rule.protocol_id,
                                                            current_message_rule.msg_id,
                                                            rule.schema_ref,
                                                            raw_data,
                                                            strategy);
        if (resolved.first >= 0 && resolved.second > 0) {
            actual_offset = resolved.first;
            field_size = resolved.second;
        }
    }

    if (actual_offset == -1) {
        // 动态偏移量
        if (rule.data_type == "currency_statistics") {
            // 币种统计起始位置：currency_count(1字节)之后
            // 34字节头 + info_type(1) + packet_flag(1) + work_mode(1) + business_mode(1) + add_up_switch(1) + counting_time(6) + duration_ms(4) + total_notes_count(2) = 51
            size_t currency_count_offset = 51;
            if (raw_data.size() < currency_count_offset + 1) {
                return std::nullopt;
            }
            actual_offset = static_cast<int>(currency_count_offset + 1);
        } else if (rule.data_type == "note_details") {
            // note_details起始位置：currency_count后 + 币种统计区（按配置记录长度）
            // currency_count绝对偏移：34字节头 + info_type(1)+packet_flag(1)+work_mode(1)+business_mode(1)+add_up_switch(1)+counting_time(6)+duration_ms(4)+total_notes_count(2) = 51
            size_t currency_count_offset = 51;
            uint8_t currency_count = 0;
            if (raw_data.size() >= currency_count_offset + 1) {
                currency_count = raw_data[currency_count_offset];
            }
            size_t statistics_start_offset = currency_count_offset + 1;
            size_t currency_record_size = GetCompositeFieldRecordSize("currency_statistics");
            if (currency_record_size == 0) {
                currency_record_size = 14;
            }
            size_t statistics_size = static_cast<size_t>(currency_count) * currency_record_size;
            actual_offset = static_cast<int>(statistics_start_offset + statistics_size);
        } else {
            // 其他动态字段按照offset_ref求结束偏移
            actual_offset = CalculateFieldEndOffset(rule.offset_ref, extracted_fields, current_message_rule);
            if (actual_offset < 0) {
                return std::nullopt; // 无法计算偏移量
            }
        }
    } else if (actual_offset < 0) {
        // 对于钞票明细数据，需要根据币种统计数据的实际大小来计算偏移量
        if (rule.data_type == "note_details") {
            // currency_count绝对偏移：34字节头 + info_type(1)+packet_flag(1)+work_mode(1)+business_mode(1)+add_up_switch(1)+counting_time(6)+duration_ms(4)+total_notes_count(2) = 51
            size_t currency_count_offset = 51;
            uint8_t currency_count = 0;
            if (raw_data.size() >= currency_count_offset + 1) {
                currency_count = raw_data[currency_count_offset];
            }
            
            // 计算币种统计数据的大小
            size_t statistics_start_offset = currency_count_offset + 1; // currency_count后的位置
            size_t currency_record_size = GetCompositeFieldRecordSize("currency_statistics");
            if (currency_record_size == 0) {
                currency_record_size = 14;
            }
            size_t statistics_size = static_cast<size_t>(currency_count) * currency_record_size;
            actual_offset = statistics_start_offset + statistics_size;
        } else {
            actual_offset = static_cast<int>(raw_data.size()) + actual_offset;
        }
    }
    
    // 移除 total_notes_count 冗余调试输出
    
    // 计算字段大小（若schema未能解析，按原逻辑计算）
    if (rule.size_ref.size() > 0 && rule.data_type == "currency_statistics") {
        // currency_statistics 是固定长度记录，可以使用 CalculateVariableFieldSize
        field_size = CalculateVariableFieldSize(rule.size_ref, raw_data, strategy);
    } else if (rule.size_ref.size() > 0 && rule.data_type == "note_details") {
        // note_details 是变长记录，使用剩余数据但保留末尾 CRC16(2) + tail(2)
        size_t available_size = raw_data.size() - static_cast<size_t>(actual_offset);
        if (raw_data.size() >= 4 && available_size >= 4) {
            available_size -= 4; // 预留 CRC16(2) + tail(2)
        }
        field_size = available_size;
    } else if (!rule.size_ref.empty()) {
        field_size = GetVariableStringLength(rule.size_ref, extracted_fields, strategy);
    }
    // 边界检查
    if (actual_offset < 0 || actual_offset + static_cast<int>(field_size) > static_cast<int>(raw_data.size())) {
        return std::nullopt;
    }
    // 提取原始数据
    std::vector<uint8_t> field_data(raw_data.begin() + actual_offset, 
                                   raw_data.begin() + actual_offset + field_size);
    // 转换字段值，传递字段名用于特殊处理
    return ParseFieldValue(field_data, rule.data_type, rule.endianness, rule.field_name);
}

std::optional<FieldValue> UniversalParser::ParseFieldValue(const std::vector<uint8_t>& raw_data,
                                                           const std::string& data_type,
                                                           const std::string& endianness,
                                                           const std::string& field_name) const {
    try {
        // 对于字符串类型,空数据是合法的(长度为0的字符串)
        if (data_type == "string" || data_type == "variable_string") {
            // 对于字符串,允许空数据(返回空字符串)
            if (raw_data.empty()) {
                return std::string("");
            }
            
            // 对于设备ID字段，保持原始长度，不清理填充字符
            if (field_name == "devUniqueId") {
                // 设备ID字段：保持完整的24字节长度，不去除任何字节
                return std::string(reinterpret_cast<const char*>(raw_data.data()), raw_data.size());
            } else if (field_name == "currency_symbol") {
                // 币种符号字段：只去除尾部的空字节，保留前导有效字符
                std::string result(reinterpret_cast<const char*>(raw_data.data()), raw_data.size());
                while (!result.empty() && result.back() == '\0') {
                    result.pop_back();
                }
                return result;
            } else {
                // 其他字符串字段：使用CleanString函数来处理填充值和乱码字符
                return MessageUtils::CleanString(raw_data);
            }
        }
        
        // 其他数据类型,空数据不合法
        if (raw_data.empty()) {
            return std::nullopt;
        }
        
        if (data_type == "uint8") {
            if (raw_data.size() >= 1) {
                return static_cast<uint8_t>(raw_data[0]);
            }
        } else if (data_type == "uint16") {
            if (raw_data.size() >= 2) {
                uint16_t value = 0;
                if (endianness == "little") {
                    value = (static_cast<uint16_t>(raw_data[1]) << 8) | 
                            static_cast<uint16_t>(raw_data[0]);
                } else {
                    value = (static_cast<uint16_t>(raw_data[0]) << 8) | 
                            static_cast<uint16_t>(raw_data[1]);
                }
                return value;
            }
        } else if (data_type == "uint32") {
            if (raw_data.size() >= 4) {
                uint32_t value = 0;
                if (endianness == "little") {
                    value = (static_cast<uint32_t>(raw_data[3]) << 24) |
                           (static_cast<uint32_t>(raw_data[2]) << 16) |
                           (static_cast<uint32_t>(raw_data[1]) << 8) |
                           static_cast<uint32_t>(raw_data[0]);
                } else {
                    value = (static_cast<uint32_t>(raw_data[0]) << 24) |
                           (static_cast<uint32_t>(raw_data[1]) << 16) |
                           (static_cast<uint32_t>(raw_data[2]) << 8) |
                           static_cast<uint32_t>(raw_data[3]);
                }
                return value;
            }
        } else if (data_type == "uint64") {
            if (raw_data.size() >= 8) {
                uint64_t value = 0;
                if (endianness == "little") {
                    value = (static_cast<uint64_t>(raw_data[7]) << 56) |
                            (static_cast<uint64_t>(raw_data[6]) << 48) |
                            (static_cast<uint64_t>(raw_data[5]) << 40) |
                            (static_cast<uint64_t>(raw_data[4]) << 32) |
                            (static_cast<uint64_t>(raw_data[3]) << 24) |
                            (static_cast<uint64_t>(raw_data[2]) << 16) |
                            (static_cast<uint64_t>(raw_data[1]) << 8) |
                            static_cast<uint64_t>(raw_data[0]);
                } else {
                    value = (static_cast<uint64_t>(raw_data[0]) << 56) |
                            (static_cast<uint64_t>(raw_data[1]) << 48) |
                            (static_cast<uint64_t>(raw_data[2]) << 40) |
                            (static_cast<uint64_t>(raw_data[3]) << 32) |
                            (static_cast<uint64_t>(raw_data[4]) << 24) |
                            (static_cast<uint64_t>(raw_data[5]) << 16) |
                            (static_cast<uint64_t>(raw_data[6]) << 8) |
                            static_cast<uint64_t>(raw_data[7]);
                }
                return value;
            }
        } else if (data_type == "bytes") {
            return raw_data;
        } else if (data_type == "bcd_datetime") {
            // BCD格式时间解析：YYMMDDHHMMSS (6字节)
            if (raw_data.size() >= 6) {
                std::ostringstream oss;
                for (size_t i = 0; i < 6; ++i) {
                    uint8_t byte = raw_data[i];
                    uint8_t high = (byte >> 4) & 0x0F;
                    uint8_t low = byte & 0x0F;
                    
                    // 验证BCD格式的有效性
                    if (high > 9 || low > 9) {
                        return std::nullopt;
                    }
                    
                    oss << static_cast<int>(high) << static_cast<int>(low);
                }
                return oss.str();
            }
        } else if (data_type == "currency_statistics") {
            // 币种统计数据解析
            return ParseCompositeField(raw_data, data_type, endianness);
        } else if (data_type == "note_details") {
            // 钞票明细数据解析
            return ParseCompositeField(raw_data, data_type, endianness);
        }
        
    } catch (const std::exception& e) {
        std::cout << "ERROR: Exception in ParseFieldValue: " << e.what() << std::endl;
    }
    
    return std::nullopt;
}

std::optional<FieldValue> UniversalParser::HandleSpecialFields(const std::string& field_name,
                                                             const std::vector<uint8_t>& raw_data,
                                                             const MessageParsingRule& rule,
                                                             const ProtocolParsingStrategy& strategy) const {
    (void)field_name;  // 避免未使用参数警告
    (void)raw_data;    // 避免未使用参数警告
    (void)rule;        // 避免未使用参数警告
    (void)strategy;    // 避免未使用参数警告
    // 这里可以处理特殊的复合字段，如点钞数据的数组
    // 暂时返回空值，后续可以根据需要扩展
    return std::nullopt;
}

std::pair<std::string, std::string> UniversalParser::ParseFieldPath(const std::string& source_path) const {
    size_t dot_pos = source_path.find('.')
;
    if (dot_pos == std::string::npos) {
        return {"", source_path};
    }
    
    std::string section = source_path.substr(0, dot_pos);
    std::string field_name = source_path.substr(dot_pos + 1);
    return {section, field_name};
}

size_t UniversalParser::CalculateVariableFieldSize(const std::string& size_ref, 
                                                  const std::vector<uint8_t>& raw_data,
                                                  const ProtocolParsingStrategy& strategy) const {
    (void)strategy;  // 避免未使用参数警告
    // 查找对应的字段规则以获取size_ref_config
    for (const auto& [msg_id, rule] : message_rules_) {
        for (const auto& field_rule : rule.fields) {
            if (field_rule.size_ref == size_ref && field_rule.size_ref_config.has_value()) {
                const auto& config = field_rule.size_ref_config.value();
                

                
                // 检查数据长度是否足够
                if (raw_data.size() < static_cast<size_t>(config.offset + config.size)) {
                    return 0;
                }
                
                // 根据数据类型解析引用字段的值
                uint64_t count = 0;
                if (config.data_type == "uint8") {
                    count = raw_data[config.offset];
                } else if (config.data_type == "uint16") {
                    if (config.size == 2) {
                        count = (static_cast<uint16_t>(raw_data[config.offset + 1]) << 8) | 
                               static_cast<uint16_t>(raw_data[config.offset]);
                    }
                } else if (config.data_type == "uint32") {
                    if (config.size == 4) {
                        count = (static_cast<uint32_t>(raw_data[config.offset + 3]) << 24) |
                               (static_cast<uint32_t>(raw_data[config.offset + 2]) << 16) |
                               (static_cast<uint32_t>(raw_data[config.offset + 1]) << 8) |
                               static_cast<uint32_t>(raw_data[config.offset]);
                    }
                } else if (config.data_type == "uint64") {
                    if (config.size == 8) {
                        count = (static_cast<uint64_t>(raw_data[config.offset + 7]) << 56) |
                                (static_cast<uint64_t>(raw_data[config.offset + 6]) << 48) |
                                (static_cast<uint64_t>(raw_data[config.offset + 5]) << 40) |
                                (static_cast<uint64_t>(raw_data[config.offset + 4]) << 32) |
                                (static_cast<uint64_t>(raw_data[config.offset + 3]) << 24) |
                                (static_cast<uint64_t>(raw_data[config.offset + 2]) << 16) |
                                (static_cast<uint64_t>(raw_data[config.offset + 1]) << 8) |
                                static_cast<uint64_t>(raw_data[config.offset]);
                    }
                }
                
                // 移除冗余调试输出
                
                size_t total_size = static_cast<size_t>(count) * static_cast<size_t>(config.record_size);
                
                // 返回总大小：记录数 × 每条记录的大小
                return total_size;
            }
        }
    }
    
    return 0;
}

size_t UniversalParser::GetVariableStringLength(const std::string& size_ref, 
                                               const std::map<std::string, FieldValue>& extracted_fields,
                                               const ProtocolParsingStrategy& strategy) const {
    (void)strategy;  // 避免未使用参数警告
    
    // 直接从已解析的字段中获取长度值
    auto it = extracted_fields.find(size_ref);
    if (it != extracted_fields.end()) {
        if (std::holds_alternative<uint8_t>(it->second)) {
            return static_cast<size_t>(std::get<uint8_t>(it->second));
        } else if (std::holds_alternative<uint16_t>(it->second)) {
            return static_cast<size_t>(std::get<uint16_t>(it->second));
        } else if (std::holds_alternative<uint32_t>(it->second)) {
            return static_cast<size_t>(std::get<uint32_t>(it->second));
        } else if (std::holds_alternative<uint64_t>(it->second)) {
            return static_cast<size_t>(std::get<uint64_t>(it->second));
        }
    }
    
    return 0;
}

void UniversalParser::InitializeCRCTable() {
    // 使用与Python版本完全相同的预定义CRC16表
    crc_table_ = {
        0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF, 0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDbe5,
        0xE97E, 0xF8F7, 0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E, 0x9CC9, 0x8D40, 0xBFDB, 0xAE52,
        0xDAED, 0xCB64, 0xF9FF, 0xE876, 0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD, 0xAD4A, 0xBCC3,
        0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5, 0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
        0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974, 0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9,
        0x2732, 0x36BB, 0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3, 0x5285, 0x430C, 0x7197, 0x601E,
        0x14A1, 0x0528, 0x37B3, 0x263A, 0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72, 0x6306, 0x728F,
        0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9, 0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
        0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738, 0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862,
        0x9AF9, 0x8B70, 0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7, 0x0840, 0x19C9, 0x2B52, 0x3ADB,
        0x4E64, 0x5FED, 0x6D76, 0x7CFF, 0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036, 0x18C1, 0x0948,
        0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E, 0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
        0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD, 0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226,
        0xD0BD, 0xC134, 0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C, 0xC60C, 0xD785, 0xE51E, 0xF497,
        0x8028, 0x91A1, 0xA33A, 0xB2B3, 0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB, 0xD68D, 0xC704,
        0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232, 0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
        0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1, 0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB,
        0x0E70, 0x1FF9, 0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330, 0x7BC7, 0x6A4E, 0x58D5, 0x495C,
        0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
    };
}

uint16_t UniversalParser::CalculateCRC16(const uint8_t* data, size_t size) const {
    uint16_t crc = 0xFFFF;
    
    for (size_t i = 0; i < size; ++i) {
        crc = static_cast<uint16_t>((crc >> 8) ^ crc_table_[(crc ^ data[i]) & 0xFF]);
    }
    
    // 返回时取反
    return static_cast<uint16_t>(~crc & 0xFFFF);
}

bool UniversalParser::ValidateCRC(const uint8_t* data, size_t size) const {
    if (size < 4) return false; // 至少需要CRC(2字节) + 报尾(2字节)
    
    // 根据协议规范，CRC校验范围：从报头到校验位前一字节
    // 报文结构：报头(2) + 类型(1) + 长度(2) + 属性(1) + ID(2) + 设备ID(24) + 流水号(2) + 报文体(N) + CRC16(2) + 报尾(2)
    // CRC位置：倒数第4-3字节
    // 报尾位置：倒数第2-1字节
    
    // 提取接收到的CRC（倒数第4-3字节）
    uint16_t received_crc = static_cast<uint16_t>(data[size-4]) | (static_cast<uint16_t>(data[size-3]) << 8);
    
    // 计算CRC（从报头到报文体结束，不包括CRC和报尾）
    uint16_t calculated_crc = CalculateCRC16(data, size - 4);
    
    return received_crc == calculated_crc;
}

std::string UniversalParser::Base64Encode(const std::vector<uint8_t>& data) const {
    static const std::string base64_chars = 
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789+/";
    
    std::string result;
    int val = 0, valb = -6;
    for (unsigned char c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            result.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) result.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (result.size() % 4) result.push_back('=');
    return result;
} 

std::optional<FieldValue> UniversalParser::ParseCurrencyStatistics(const std::vector<uint8_t>& raw_data, 
                                                                 const std::string& endianness) const {
    // 使用配置驱动的解析方法
    return ParseCompositeField(raw_data, "currency_statistics", endianness);
}

std::optional<FieldValue> UniversalParser::ParseNoteDetails(const std::vector<uint8_t>& raw_data, 
                                                          const std::string& endianness) const {
    // 使用配置驱动的解析方法
    return ParseCompositeField(raw_data, "note_details", endianness);
}

std::optional<FieldValue> UniversalParser::ParseCompositeField(const std::vector<uint8_t>& raw_data,
                                                             const std::string& field_type,
                                                             const std::string& endianness) const {
    (void)endianness;  // 避免未使用参数警告
    // 查找复合字段类型定义
    auto it = composite_field_types_.find(field_type);
    if (it == composite_field_types_.end()) {
        return std::nullopt;
    }
    
    const auto& composite_type = it->second;
    
    // 检查是否包含变长字段
    bool has_variable_field = false;
    for (const auto& field : composite_type.structure) {
        if (!field.size_ref.empty()) {
            has_variable_field = true;
            break;
        }
    }
    
    // 计算每条记录的总大小（仅对固定长度记录）
    size_t record_size = 0;
    if (!has_variable_field) {
        for (const auto& field : composite_type.structure) {
            record_size += field.size;
        }
        
        if (record_size == 0) {
            return std::nullopt;
        }
    }
    
    // 根据字段类型选择不同的解析逻辑
    if (field_type == "currency_statistics") {
        std::vector<CountInfo> statistics;
        size_t offset = 0;
        
        // currency_statistics 是固定长度记录
        if (record_size == 0) {
            return std::nullopt;
        }
        
        while (offset + record_size <= raw_data.size()) {
            CountInfo info;
            size_t field_offset = 0;
            
            for (const auto& field : composite_type.structure) {
                if (offset + field_offset + field.size > raw_data.size()) {
                    break;
                }
                
                std::vector<uint8_t> field_data(raw_data.begin() + offset + field_offset,
                                               raw_data.begin() + offset + field_offset + field.size);
                

                
                auto field_value = ParseFieldValue(field_data, field.type, field.endianness, field.name);
                if (field_value.has_value()) {
                    if (field.name == "currency_symbol") {
                        // 对于币种符号字段，使用特殊处理，保持原始值
                        std::string currency_symbol = std::get<std::string>(field_value.value());
                        if (currency_symbol.empty()) {
                            // 如果为空，尝试从原始数据中提取，不进行清理
                            currency_symbol = std::string(reinterpret_cast<const char*>(field_data.data()), field_data.size());
                            // 去除尾随的空字节，但保留前导的有效字符
                            while (!currency_symbol.empty() && currency_symbol.back() == '\0') {
                                currency_symbol.pop_back();
                            }
                        }
                        info.currency_symbol = currency_symbol;
                    } else if (field.name == "count") {
                        info.count = std::get<uint16_t>(field_value.value());
                    } else if (field.name == "amount") {
                        if (std::holds_alternative<uint64_t>(field_value.value())) {
                            info.amount = std::get<uint64_t>(field_value.value());
                        } else if (std::holds_alternative<uint32_t>(field_value.value())) {
                            info.amount = std::get<uint32_t>(field_value.value());
                        }
                    }
                }
                
                field_offset += field.size;
            }
            
            statistics.push_back(info);
            offset += record_size;
        }
        

        return statistics;
    } else if (field_type == "note_details") {
        std::vector<NoteInfo> details;
        size_t offset = 0;

        // 新协议支持变长记录(error_code为变长字符串),逐条解析直到数据耗尽
        while (offset < raw_data.size()) {
            NoteInfo info;
            size_t field_offset = offset;
            bool record_valid = true;
            uint8_t error_code_length = 0;

            for (const auto& field : composite_type.structure) {
                // 计算当前字段的实际大小
                size_t actual_field_size = 0;
                if (!field.size_ref.empty()) {
                    // 变长字段：大小由之前解析的长度字段决定
                    if (field.size_ref == "error_code_length") {
                        actual_field_size = error_code_length;
                    } else {
                        // 其他size_ref暂不支持
                        record_valid = false;
                        break;
                    }
                } else if (field.size > 0) {
                    // 固定长度字段
                    actual_field_size = static_cast<size_t>(field.size);
                } else {
                    // 如果size为0且没有size_ref，跳过
                    record_valid = false;
                    break;
                }

                if (field_offset + static_cast<size_t>(actual_field_size) > raw_data.size()) {
                    // 边界检查：数据不足，停止解析
                    record_valid = false;
                    break;
                }

                std::vector<uint8_t> field_data(raw_data.begin() + field_offset,
                                               raw_data.begin() + field_offset + actual_field_size);

                auto field_value = ParseFieldValue(field_data, field.type, field.endianness, field.name);
                if (field_value.has_value()) {
                    if (field.name == "currency_symbol") {
                        std::string currency_symbol;
                        if (std::holds_alternative<std::string>(field_value.value())) {
                            currency_symbol = std::get<std::string>(field_value.value());
                        }
                        if (currency_symbol.empty()) {
                            currency_symbol = std::string(reinterpret_cast<const char*>(field_data.data()),
                                                          std::min(field_data.size(), static_cast<size_t>(actual_field_size)));
                            while (!currency_symbol.empty() && currency_symbol.back() == '\0') {
                                currency_symbol.pop_back();
                            }
                        }
                        info.currency_symbol = currency_symbol;
                    } else if (field.name == "denomination") {
                        if (std::holds_alternative<uint32_t>(field_value.value())) {
                            info.denomination = std::get<uint32_t>(field_value.value());
                        }
                    } else if (field.name == "note_version") {
                        if (std::holds_alternative<uint8_t>(field_value.value())) {
                            info.note_version = std::get<uint8_t>(field_value.value());
                        }
                    } else if (field.name == "error_group") {
                        if (std::holds_alternative<uint8_t>(field_value.value())) {
                            info.error_group = std::get<uint8_t>(field_value.value());
                        }
                    } else if (field.name == "error_type") {
                        if (std::holds_alternative<uint16_t>(field_value.value())) {
                            info.error_type = std::get<uint16_t>(field_value.value());
                        }
                    } else if (field.name == "error_code_length") {
                        if (std::holds_alternative<uint8_t>(field_value.value())) {
                            error_code_length = std::get<uint8_t>(field_value.value());
                        }
                    } else if (field.name == "error_code") {
                        if (std::holds_alternative<std::string>(field_value.value())) {
                            info.error_code = std::get<std::string>(field_value.value());
                        }
                    } else if (field.name == "serial_number") {
                        if (std::holds_alternative<std::string>(field_value.value())) {
                            info.serial_number = std::get<std::string>(field_value.value());
                        }
                    } else if (field.name == "stacker") {
                        if (std::holds_alternative<uint8_t>(field_value.value())) {
                            info.stacker = std::get<uint8_t>(field_value.value());
                        }
                    }
                } else {
                    record_valid = false;
                    break;
                }

                field_offset += actual_field_size;
            }

            if (record_valid) {
                details.push_back(info);
            } else {
                // 解析失败,停止继续解析
                break;
            }

            offset = field_offset;
        }

        return details;
    }
    
    return std::nullopt;
}

size_t UniversalParser::GetCompositeFieldRecordSize(const std::string& field_type) const {
    auto it = composite_field_types_.find(field_type);
    if (it == composite_field_types_.end()) {
        return 0;
    }

    size_t total_size = 0;
    for (const auto& field : it->second.structure) {
        if (field.size > 0) {
            total_size += static_cast<size_t>(field.size);
        }
    }
    return total_size;
}

int UniversalParser::CalculateFieldEndOffset(const std::string& field_name_to_find_end_of,
                                             const std::map<std::string, FieldValue>& extracted_fields,
                                             const MessageParsingRule& current_message_rule) const {
    // 在当前消息规则中查找引用字段
    for (const auto& ref_field_rule : current_message_rule.fields) {
        if (ref_field_rule.field_name == field_name_to_find_end_of) {
            // 计算引用字段的起始偏移量
            int ref_field_start_offset;
            if (ref_field_rule.offset == -1) {
                // 这个字段本身也是动态的，递归计算其起始偏移量
                ref_field_start_offset = CalculateFieldEndOffset(ref_field_rule.offset_ref, extracted_fields, current_message_rule);
                if (ref_field_start_offset < 0) return -1; // 递归调用出错
            } else {
                ref_field_start_offset = ref_field_rule.offset;
            }
            
            // 计算引用字段的实际长度
            int ref_field_actual_length = 0;
            if (ref_field_rule.data_type == "variable_string" && !ref_field_rule.size_ref.empty()) {
                // 变长字符串：从已解析的字段中获取实际长度
                if (extracted_fields.count(ref_field_rule.size_ref)) {
                    const auto& length_val = extracted_fields.at(ref_field_rule.size_ref);
                    if (std::holds_alternative<uint8_t>(length_val)) {
                        ref_field_actual_length = std::get<uint8_t>(length_val);
                    } else if (std::holds_alternative<uint16_t>(length_val)) {
                        ref_field_actual_length = std::get<uint16_t>(length_val);
                    } else if (std::holds_alternative<uint32_t>(length_val)) {
                        ref_field_actual_length = std::get<uint32_t>(length_val);
                    } else if (std::holds_alternative<uint64_t>(length_val)) {
                        auto len64 = std::get<uint64_t>(length_val);
                        if (len64 > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
                            return -1;
                        }
                        ref_field_actual_length = static_cast<int>(len64);
                    } else {
                        // 长度字段存在但不是有效的整数类型
                        return -1;
                    }
                } else {
                    // 长度字段在extracted_fields中未找到（如果解析顺序正确，不应该发生）
                    return -1;
                }
            } else if (ref_field_rule.data_type == "uint8" || ref_field_rule.data_type == "uint16" ||
                       ref_field_rule.data_type == "uint32" || ref_field_rule.data_type == "uint64") {
                // 固定长度的数值字段：使用规则中定义的大小
                ref_field_actual_length = ref_field_rule.size;
            } else {
                // 其他固定长度字段：使用规则中定义的大小
                ref_field_actual_length = ref_field_rule.size;
            }
            
            // 返回引用字段的结束位置
            return ref_field_start_offset + ref_field_actual_length;
        }
    }
    
    return -1; // 在当前消息规则中未找到引用字段
}

std::pair<int, size_t> UniversalParser::ResolveFieldOffsetAndSizeFromSchema(const std::string& protocol_id,
                                                                            uint16_t msg_id,
                                                                            const std::string& schema_field_name,
                                                                            const std::vector<uint8_t>& raw_data,
                                                                            const ProtocolParsingStrategy& strategy) const {
    // 安全兜底：若未加载schema或未开启，则返回失败
    auto schema_it = protocol_schemas_.find(protocol_id);
    if (schema_it == protocol_schemas_.end()) {
        return {-1, 0};
    }
    const json& schema = schema_it->second;
    
    try {
        // header固定大小
        int offset = strategy.header_size;
        size_t size = 0;
        
        // 找到消息体定义数组
        if (!schema.contains("messages") || !schema["messages"].contains("bodies")) {
            return {-1, 0};
        }
        const auto& bodies = schema["messages"]["bodies"];
        std::string msg_key = std::to_string(msg_id);
        if (!bodies.contains(msg_key) || !bodies[msg_key].is_array()) {
            return {-1, 0};
        }
        const auto& fields = bodies[msg_key];
        
        // 遍历字段，顺序累加，支持长度引用
        for (const auto& f : fields) {
            std::string name = f.value("name", "");
            // 获取size可能是数字或字符串（引用）
            size_t fsize = 0;
            if (f["size"].is_number()) {
                fsize = f["size"].get<int>();
            } else if (f["size"].is_string()) {
                std::string ref = f["size"].get<std::string>();
                // 从raw_data中，根据此前字段累积位置读取ref长度值
                // 简化：常见ref为B或H，按小端读取
                // 先在已遍历字段中查找该ref对应的起始offset
                int ref_offset = strategy.header_size;
                for (const auto& pf : fields) {
                    std::string pname = pf.value("name", "");
                    if (pname == ref) break;
                    if (pf["size"].is_number()) {
                        ref_offset += pf["size"].get<int>();
                    } else if (pf["size"].is_string()) {
                        // 嵌套引用：保守返回失败，避免错误推导
                        return {-1, 0};
                    }
                }
                if (ref == "hardwareVersionLength") {
                    if (ref_offset + 1 <= (int)raw_data.size()) fsize = raw_data[ref_offset]; else return {-1, 0};
                } else if (ref == "mainSoftwareVersionLength" || ref == "currencyDbVersionLength") {
                    if (ref_offset + 2 <= (int)raw_data.size()) {
                        fsize = (static_cast<uint16_t>(raw_data[ref_offset+1]) << 8) | raw_data[ref_offset];
                    } else return {-1, 0};
                } else if (ref == "additional_msg_length" || ref == "failure_desc_length" || ref == "branchInfoLength") {
                    if (ref_offset + 1 <= (int)raw_data.size()) fsize = raw_data[ref_offset]; else return {-1, 0};
                } else {
                    // 未知引用：兜底失败
                    return {-1, 0};
                }
            }
            
            if (name == schema_field_name) {
                size = fsize;
                return {offset, size};
            }
            offset += static_cast<int>(fsize);
        }
    } catch (...) {
        return {-1, 0};
    }
    return {-1, 0};
}
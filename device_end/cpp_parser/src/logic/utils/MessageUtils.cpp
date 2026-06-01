#include "logic/utils/MessageUtils.h"
#include "logic/UniversalParser.h"
#include <type_traits>
#include <cstring>

std::string MessageUtils::VecToReadable(const std::vector<uint8_t>& v) {
    if (v.empty()) return std::string("");
    
    // 检查是否为常见的填充值（全0x00、全0xFF、全0x20空格等）
    bool is_all_same = true;
    uint8_t first_byte = v[0];
    
    // 检查是否所有字节都相同
    for (size_t i = 1; i < v.size(); ++i) {
        if (v[i] != first_byte) {
            is_all_same = false;
            break;
        }
    }
    
    // 如果是全相同的填充值，返回空字符串
    if (is_all_same && (first_byte == 0x00 || first_byte == 0xFF || first_byte == 0x20)) {
        return std::string("");
    }
    
    if (v.size() == 1) return std::to_string(static_cast<int>(v[0]));
    if (v.size() == 2) {
        int val = static_cast<int>(v[0] | (v[1] << 8));
        return std::to_string(val);
    }
    
    size_t real_len = v.size();
    while (real_len > 0 && v[real_len - 1] == 0x00) --real_len;
    bool printable = std::all_of(v.begin(), v.begin() + real_len, [](uint8_t c) { 
        return c >= 0x20 && c <= 0x7e; 
    });
    
    if (printable) return std::string(reinterpret_cast<const char*>(v.data()), real_len);
    
    std::ostringstream oss;
    for (auto b : v) oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b) << ' ';
    return oss.str();
}

std::string MessageUtils::MessageToJson(const UniversalParsedMessage& parsed_msg) {
    nlohmann::json dump_json;
    for (const auto& [k, v] : parsed_msg.extracted_fields) {
        // 根据字段类型进行序列化
        std::visit([&dump_json, &k](const auto& value) {
            using T = std::decay_t<decltype(value)>;
            if constexpr (std::is_same_v<T, std::vector<CountInfo>>) {
                // 自定义序列化 CountInfo 向量
                nlohmann::json array = nlohmann::json::array();
                for (const auto& item : value) {
                    nlohmann::json item_json;
                    item_json["currency_symbol"] = item.currency_symbol;
                    item_json["count"] = item.count;
                    item_json["amount"] = item.amount;
                    array.push_back(item_json);
                }
                dump_json["fields"][k] = array;
            } else if constexpr (std::is_same_v<T, std::vector<NoteInfo>>) {
                // 自定义序列化 NoteInfo 向量
                nlohmann::json array = nlohmann::json::array();
                

                for (const auto& item : value) {
                    nlohmann::json item_json;
                    item_json["currency_symbol"] = item.currency_symbol;
                    item_json["denomination"] = item.denomination;
                    item_json["note_version"] = item.note_version;
                    item_json["error_group"] = item.error_group;
                    item_json["error_type"] = item.error_type;
                    item_json["error_code"] = item.error_code;
                    item_json["serial_number"] = item.serial_number;
                    item_json["stacker"] = item.stacker;
                    array.push_back(item_json);
                }
                dump_json["fields"][k] = array;
            } else if constexpr (std::is_same_v<T, std::string>) {
                // 对字符串进行特殊处理，检查是否包含非UTF-8字符
                bool is_valid_utf8 = true;
                for (char c : value) {
                    if (static_cast<uint8_t>(c) > 0x7F) {
                        is_valid_utf8 = false;
                        break;
                    }
                }
                
                if (is_valid_utf8) {
                    dump_json["fields"][k] = value;
                } else {
                    // 转换为十六进制字符串
                    std::ostringstream oss;
                    oss << "0x";
                    for (char c : value) {
                        oss << std::hex << std::setw(2) << std::setfill('0') 
                            << static_cast<int>(static_cast<uint8_t>(c));
                    }
                    dump_json["fields"][k] = oss.str();
                }
            } else {
                // 其他类型直接序列化
                dump_json["fields"][k] = value;
            }
        }, v);
    }
    dump_json["msg_id"] = parsed_msg.msg_id;
    dump_json["source_ip"] = parsed_msg.source_ip;
    dump_json["raw_data_base64"] = parsed_msg.raw_data_base64;
    dump_json["is_valid"] = parsed_msg.is_valid;
    dump_json["error_message"] = parsed_msg.error_message;
    return dump_json.dump(2);
}

std::string MessageUtils::VecToHexString(const std::vector<uint8_t>& v) {
    std::ostringstream oss;
    for (auto b : v) {
        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b);
    }
    return oss.str();
}

std::vector<uint8_t> MessageUtils::HexStringToVec(const std::string& hex_str) {
    std::vector<uint8_t> result;
    for (size_t i = 0; i < hex_str.length(); i += 2) {
        std::string byte_str = hex_str.substr(i, 2);
        result.push_back(static_cast<uint8_t>(std::stoi(byte_str, nullptr, 16)));
    }
    return result;
} 

std::string MessageUtils::CleanString(const std::vector<uint8_t>& data) {
    if (data.empty()) {
        return "";
    }
    
    // 检查是否为常见的填充值（全0x00、全0xFF、全0x20空格等）
    bool is_all_same = true;
    uint8_t first_byte = data[0];
    
    // 检查是否所有字节都相同
    for (size_t i = 1; i < data.size(); ++i) {
        if (data[i] != first_byte) {
            is_all_same = false;
            break;
        }
    }
    
    // 如果是全相同的填充值，返回空字符串
    if (is_all_same && (first_byte == 0x00 || first_byte == 0xFF || first_byte == 0x20)) {
        return "";
    }
    
    // 去除尾随的空字节
    size_t real_len = data.size();
    while (real_len > 0 && data[real_len - 1] == 0x00) {
        --real_len;
    }
    
    if (real_len == 0) {
        return "";
    }
    
    // 更宽松的字符过滤：保留可打印的ASCII字符、控制字符和扩展ASCII字符
    std::string result;
    for (size_t i = 0; i < real_len; ++i) {
        uint8_t byte = data[i];
        // 保留可打印的ASCII字符 (0x20-0x7E)、控制字符和扩展ASCII字符 (0x80-0xFE)，但排除0xFF
        if ((byte >= 0x20 && byte <= 0x7E) || 
            byte == 0x01 || byte == 0x02 || byte == 0x03 || 
            byte == 0x09 || byte == 0x0A || byte == 0x0D || // tab, newline, carriage return
            (byte >= 0x80 && byte <= 0xFE)) { // 扩展ASCII字符，包括中文字符等，但排除0xFF
            result += static_cast<char>(byte);
        }
    }
    
    // 如果过滤后为空，返回空字符串
    if (result.empty()) {
        return "";
    }
    
    return result;
}

std::string MessageUtils::CleanString(const std::string& str) {
    if (str.empty()) {
        return "";
    }
    
    // 去除尾随的空字节和空格
    std::string result = str;
    while (!result.empty() && (result.back() == '\0' || result.back() == ' ')) {
        result.pop_back();
    }
    
    if (result.empty()) {
        return "";
    }
    
    // 更宽松的字符过滤：保留可打印的ASCII字符、控制字符和扩展ASCII字符
    std::string filtered_result;
    for (char c : result) {
        uint8_t byte = static_cast<uint8_t>(c);
        // 保留可打印的ASCII字符 (0x20-0x7E)、控制字符和扩展ASCII字符 (0x80-0xFE)，但排除0xFF
        if ((byte >= 0x20 && byte <= 0x7E) || 
            byte == 0x01 || byte == 0x02 || byte == 0x03 || 
            byte == 0x09 || byte == 0x0A || byte == 0x0D || // tab, newline, carriage return
            (byte >= 0x80 && byte <= 0xFE)) { // 扩展ASCII字符，包括中文字符等，但排除0xFF
            filtered_result += c;
        }
    }
    
    // 如果过滤后为空，返回空字符串
    if (filtered_result.empty()) {
        return "";
    }
    
    return filtered_result;
} 

// UTF-8 校验
bool MessageUtils::IsValidUtf8(const std::string& s) {
    const unsigned char* bytes = reinterpret_cast<const unsigned char*>(s.data());
    size_t len = s.size();
    size_t i = 0;
    while (i < len) {
        unsigned char c = bytes[i];
        if (c <= 0x7F) { // ASCII
            i += 1; continue;
        } else if ((c >> 5) == 0x6) { // 110xxxxx 10xxxxxx
            if (i + 1 >= len) return false;
            unsigned char c1 = bytes[i+1];
            if ((c1 >> 6) != 0x2) return false;
            i += 2; continue;
        } else if ((c >> 4) == 0xE) { // 1110xxxx 10xxxxxx 10xxxxxx
            if (i + 2 >= len) return false;
            unsigned char c1 = bytes[i+1], c2 = bytes[i+2];
            if (((c1 >> 6) != 0x2) || ((c2 >> 6) != 0x2)) return false;
            // 排除 UTF-8 Overlong 或代理项范围的简单检查（可选）
            i += 3; continue;
        } else if ((c >> 3) == 0x1E) { // 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
            if (i + 3 >= len) return false;
            unsigned char c1 = bytes[i+1], c2 = bytes[i+2], c3 = bytes[i+3];
            if (((c1 >> 6) != 0x2) || ((c2 >> 6) != 0x2) || ((c3 >> 6) != 0x2)) return false;
            i += 4; continue;
        } else {
            return false;
        }
    }
    return true;
}

// 将常见 CP1252/Latin-1 的 0x80-0x9F 范围字符映射到 UTF-8；
// 其它 0xA0-0xFF 视为 ISO-8859-1 直译到 U+00A0..U+00FF。
static std::string Cp1252ToUtf8(const std::string& bytes) {
    static const char* cp1252_map[32] = {
        "\xE2\x82\xAC", "\xC2\x81",       "\xE2\x80\x9A", "\xC6\x92",
        "\xE2\x80\x9E", "\xE2\x80\xA6", "\xE2\x80\xA0", "\xE2\x80\xA1",
        "\xCB\x86",       "\xE2\x80\xB0", "\xC5\xA0",       "\xE2\x80\xB9",
        "\xC5\x92",       "\xC2\x8D",       "\xC5\xBD",       "\xC2\x8F",
        "\xC2\x90",       "\xE2\x80\x98", "\xE2\x80\x99", "\xE2\x80\x9C",
        "\xE2\x80\x9D", "\xE2\x80\xA2", "\xE2\x80\x93", "\xE2\x80\x94",
        "\xCB\x9C",       "\xE2\x84\xA2", "\xC5\xA1",       "\xE2\x80\xBA",
        "\xC5\x93",       "\xC2\x9D",       "\xC5\xBE",       "\xC5\xB8"
    }; // 0x80..0x9F

    std::string out; out.reserve(bytes.size() * 2);
    for (unsigned char ch : bytes) {
        if (ch < 0x80) {
            out.push_back(static_cast<char>(ch));
        } else if (ch >= 0x80 && ch <= 0x9F) {
            const char* m = cp1252_map[ch - 0x80];
            // 某些未定义位置（81, 8D, 8F, 90, 9D）映射到 C2 81 等保留；保留为两个字节
            out.append(m);
        } else { // 0xA0 - 0xFF 当作 ISO-8859-1 -> UTF-8
            unsigned int code = static_cast<unsigned int>(ch);
            // 两字节 UTF-8: 110xxxxx 10xxxxxx
            char b1 = static_cast<char>(0xC0 | (code >> 6));
            char b2 = static_cast<char>(0x80 | (code & 0x3F));
            out.push_back(b1); out.push_back(b2);
        }
    }
    return out;
}

static inline bool is_fill_char(unsigned char b) {
    return b == 0x00 || b == 0xFF || b == 0x20; // 空、FF、空格 作为常见填充
}

static std::string trim_trailing_fills(const std::string& s) {
    if (s.empty()) return s;
    size_t end = s.size();
    while (end > 0 && is_fill_char(static_cast<unsigned char>(s[end-1]))) {
        --end;
    }
    return s.substr(0, end);
}

std::string MessageUtils::NormalizeForDb(const std::string& s) {
    // 1) 基础清理（去尾随填充）
    std::string cleaned = trim_trailing_fills(s);
    if (cleaned.empty()) return "";

    // 2) 若已是有效 UTF-8，则直接返回（再轻微清理智能引号 -> ASCII）
    if (IsValidUtf8(cleaned)) {
        std::string out; out.reserve(cleaned.size());
        for (size_t i = 0; i < cleaned.size(); ++i) {
            unsigned char c = static_cast<unsigned char>(cleaned[i]);
            // 简单替换 Windows 智能引号对应 UTF-8 序列
            if (c == '\xE2' && i + 2 < cleaned.size()) {
                unsigned char c1 = static_cast<unsigned char>(cleaned[i+1]);
                unsigned char c2 = static_cast<unsigned char>(cleaned[i+2]);
                // 左/右单引号 U+2018/U+2019 -> '
                if (c1 == 0x80 && (c2 == 0x98 || c2 == 0x99)) { out.push_back('\''); i += 2; continue; }
                // 左/右双引号 U+201C/U+201D -> "
                if (c1 == 0x80 && (c2 == 0x9C || c2 == 0x9D)) { out.push_back('"'); i += 2; continue; }
                // 短横/长横 U+2013/U+2014 -> '-'
                if (c1 == 0x80 && (c2 == 0x93 || c2 == 0x94)) { out.push_back('-'); i += 2; continue; }
            }
            out.push_back(static_cast<char>(c));
        }
        return out;
    }

    // 3) 非 UTF-8：按 CP1252/Latin-1 转成 UTF-8
    std::string utf8 = Cp1252ToUtf8(cleaned);
    // 二次安全：再去尾随填充
    utf8 = trim_trailing_fills(utf8);
    return utf8;
}

std::string MessageUtils::NormalizeForDb(const std::vector<uint8_t>& data) {
    // 先用已有 CleanString(bytes) 去掉尾部 00 等
    std::string s = CleanString(data);
    return NormalizeForDb(s);
}
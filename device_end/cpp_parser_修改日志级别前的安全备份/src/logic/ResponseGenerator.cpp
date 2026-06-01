#include "logic/ResponseGenerator.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <ctime>
#include <chrono>
#include <algorithm>
#include <cstring>
#include <openssl/sha.h>

namespace { // 将辅助函数放入匿名命名空间
    // 辅助函数，将十六进制字符串转换为二进制字节数组
    std::vector<uint8_t> HexStringToBytes(const std::string& hex) {
        std::vector<uint8_t> bytes;
        if (hex.length() % 2 != 0) { return bytes; }
        for (unsigned int i = 0; i < hex.length(); i += 2) {
            try {
                std::string byteString = hex.substr(i, 2);
                uint8_t byte = static_cast<uint8_t>(std::stoul(byteString, nullptr, 16));
                bytes.push_back(byte);
            } catch (...) { return {}; }
        }
        return bytes;
    }

    // 从数据库提供的storage_path或ftp_dir中提取主机(及端口)后的目录部分
    // 兼容以下形式：
    //  - "/firmwares/DP-xxx.zip"
    //  - "firmwares/DP-xxx.zip"
    //  - "192.168.1.2:21/firmwares/DP-xxx.zip"
    //  - "ftp://192.168.1.2:21/firmwares/DP-xxx.zip"
    // 返回形如："/firmwares/"（确保以/开头且/结尾）
    std::string ExtractDirAfterHost(const std::string& storage_path) {
        if (storage_path.empty()) return std::string("/");
        std::string s = storage_path;

        // 定位主机部分后的第一个斜杠
        size_t pos = 0;
        size_t scheme_pos = s.find("://");
        if (scheme_pos != std::string::npos) {
            pos = scheme_pos + 3;
        }

        std::string path;
        // 若无scheme且也无主机端口分隔（无冒号），视为纯路径
        if (scheme_pos == std::string::npos && s.find(':') == std::string::npos) {
            path = s;
            if (path.empty() || path.front() != '/') path = "/" + path;
        } else {
            // 查找主机后的第一个/
            size_t slash = s.find('/', pos);
            if (slash != std::string::npos) {
                path = s.substr(slash);
            } else {
                // 没有路径，退化为根目录
                path = "/";
            }
        }

        // 去掉文件名部分（若最后一段包含.，例如.zip）
        size_t last_slash = path.rfind('/');
        if (last_slash != std::string::npos && last_slash + 1 < path.size()) {
            std::string last = path.substr(last_slash + 1);
            if (last.find('.') != std::string::npos) {
                path = path.substr(0, last_slash + 1);
            }
        }

        if (path.empty() || path.front() != '/') path = "/" + path;
        if (path.back() != '/') path.push_back('/');
        return path;
    }
}

ResponseGenerator::ResponseGenerator() {
    heart_interval_ = 180;
    keep_connect_ = 0;
}

ResponseGenerator::~ResponseGenerator() = default;

bool ResponseGenerator::Initialize(std::shared_ptr<IUniversalParser> universal_parser, 
                                   std::shared_ptr<MultiProtocolManager> protocol_manager) {
    universal_parser_ = universal_parser;
    protocol_manager_ = protocol_manager;
    return true;
}

std::vector<uint8_t> ResponseGenerator::CreateRegistrationResponse(const UniversalParsedMessage& request_msg,
                                                                  uint8_t result_code,
                                                                  const std::vector<uint8_t>& authentication_code) {
    uint16_t response_msg_id = 32770;
    std::string device_unique_id = ExtractDeviceUniqueId(request_msg);
    uint16_t seq_num = ExtractSequenceNumber(request_msg);
    try {
        std::cout << "[DEBUG] [ResponseGenerator] CreateRegistrationResponse seq=" << seq_num
                  << " result=0x" << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(result_code)
                  << std::dec << " auth_in_len=" << authentication_code.size() << std::endl;
    } catch (...) {}

    std::vector<uint8_t> auth_code_vec = authentication_code;
    if (authentication_code.empty() && (result_code == 0x00)) {
        auth_code_vec = GenerateAuthenticationCode(device_unique_id);
    }

    // 调试：打印实际使用的鉴权码
    if (!auth_code_vec.empty()) {
        std::ostringstream oss;
        oss << std::hex << std::setfill('0');
        for (auto b : auth_code_vec) {
            oss << std::setw(2) << static_cast<int>(b);
        }
        try {
            std::cout << "[DEBUG] [ResponseGenerator] Actual auth_code used in response: " << oss.str() << std::endl;
        } catch (...) {}
    }

    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["response_seNum"] = PackValue(seq_num, 2);
    body_data["result"] = PackValue(result_code, 1);
    if (!auth_code_vec.empty()) {
        body_data["authentication_code"] = auth_code_vec;
    }

    // 从请求消息中获取协议ID，如果没有则使用默认值
    std::string protocol_id = request_msg.protocol_id.empty() ? "dp_protocol_v1" : request_msg.protocol_id;

    BodyBuildContext ctx; ctx.seq_num = seq_num; ctx.result = result_code; ctx.authentication_code = auth_code_vec;
    std::vector<uint8_t> body = CreateBody(response_msg_id, body_data, protocol_id, &ctx);
    
    // 调试：打印实际用于响应的鉴权码
    if (!auth_code_vec.empty()) {
        std::ostringstream oss; oss << std::hex << std::setfill('0');
        for (auto b : auth_code_vec) oss << std::setw(2) << static_cast<int>(b);
        std::cout << "[DEBUG] [ResponseGenerator] Actual auth code in response: " << oss.str() << std::endl;
    }
    
    std::vector<uint8_t> header = CreateHeader(response_msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateLoginResponse(const UniversalParsedMessage& request_msg, uint8_t status_code, uint8_t keep_connect) {
    uint16_t response_msg_id = 32771;
    std::string device_unique_id = ExtractDeviceUniqueId(request_msg);
    uint16_t seq_num = ExtractSequenceNumber(request_msg);
    
    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["response_seNum"] = PackValue(seq_num, 2);
    body_data["result"] = PackValue(status_code, 1);
    
    if (status_code == 0x00) {
        body_data["server_time"] = GetCurrentTimeBCD();
        body_data["heart_interval"] = PackValue(heart_interval_, 1);
        body_data["keep_connect"] = PackValue(keep_connect, 1);
    }
    
    // 从请求消息中获取协议ID，如果没有则使用默认值
    std::string protocol_id = request_msg.protocol_id.empty() ? "dp_protocol_v1" : request_msg.protocol_id;
    
    BodyBuildContext ctx; ctx.seq_num = seq_num; ctx.result = status_code; ctx.keep_connect = keep_connect; ctx.heart_interval = heart_interval_;
    if (status_code == 0x00) ctx.server_time_bcd = GetCurrentTimeBCD();
    std::vector<uint8_t> body = CreateBody(response_msg_id, body_data, protocol_id, &ctx);
    std::vector<uint8_t> header = CreateHeader(response_msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateHeartbeatResponse(const UniversalParsedMessage& request_msg, uint8_t keep_connect) {
    uint16_t response_msg_id = 32772;
    std::string device_unique_id = ExtractDeviceUniqueId(request_msg);
    uint16_t seq_num = ExtractSequenceNumber(request_msg);
    
    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["response_seNum"] = PackValue(seq_num, 2);
    body_data["keep_connect"] = PackValue(keep_connect, 1);
    
    // 从请求消息中获取协议ID，如果没有则使用默认值
    std::string protocol_id = request_msg.protocol_id.empty() ? "dp_protocol_v1" : request_msg.protocol_id;
    
    BodyBuildContext ctx; ctx.seq_num = seq_num; ctx.keep_connect = keep_connect;
    std::vector<uint8_t> body = CreateBody(response_msg_id, body_data, protocol_id, &ctx);
    std::vector<uint8_t> header = CreateHeader(response_msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateGenericResponse(const UniversalParsedMessage& request_msg, uint8_t result, const std::string& additional_msg) {
    uint16_t response_msg_id = 32769;
    std::string device_unique_id = ExtractDeviceUniqueId(request_msg);
    uint16_t seq_num = ExtractSequenceNumber(request_msg);
    
    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["response_seNum"] = PackValue(seq_num, 2);
    body_data["response_msg_id"] = PackValue(request_msg.msg_id, 2);
    body_data["result"] = PackValue(result, 1);
    body_data["additional_msg_length"] = PackValue(static_cast<uint8_t>(additional_msg.length()), 1);
    body_data["additional_msg"] = PackString(additional_msg, additional_msg.length());
    
    // 从请求消息中获取协议ID，如果没有则使用默认值
    std::string protocol_id = request_msg.protocol_id.empty() ? "dp_protocol_v1" : request_msg.protocol_id;
    
    BodyBuildContext ctx; ctx.seq_num = seq_num; ctx.response_msg_id = request_msg.msg_id; ctx.result = result; ctx.additional_msg = additional_msg;
    std::vector<uint8_t> body = CreateBody(response_msg_id, body_data, protocol_id, &ctx);
    std::vector<uint8_t> header = CreateHeader(response_msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateUpgradeQueryResponse(const UniversalParsedMessage& request_msg, bool has_upgrade) {
    uint16_t response_msg_id = 32773;
    std::string device_unique_id = ExtractDeviceUniqueId(request_msg);
    uint16_t seq_num = ExtractSequenceNumber(request_msg);
    
    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["response_seNum"] = PackValue(seq_num, 2);
    body_data["result"] = PackValue(static_cast<uint8_t>(has_upgrade ? 0x00 : 0x01), 1);
    
    if (has_upgrade) {
        body_data["force_upgrade"] = PackValue(static_cast<uint8_t>(upgrade_info_.force_upgrade), 1);
        body_data["upgrade_task_id"] = PackString(upgrade_info_.task_id, 18);
        uint16_t start_time_val = static_cast<uint16_t>(upgrade_info_.time_arrange_start * 100);
        uint16_t end_time_val = static_cast<uint16_t>(upgrade_info_.time_arrange_end * 100);
        body_data["start_time"] = PackValue(start_time_val, 2);
        body_data["end_time"] = PackValue(end_time_val, 2);
        body_data["module_type"] = PackValue(upgrade_info_.module_type, 1);
        body_data["file_size"] = PackValue(static_cast<uint32_t>(upgrade_info_.file_size), 4);
        body_data["firmware_name_length"] = PackValue(static_cast<uint8_t>(upgrade_info_.firmware_name.length()), 1);
        body_data["firmware_name"] = PackString(upgrade_info_.firmware_name, upgrade_info_.firmware_name.length());
        body_data["firmware_md5"] = HexStringToBytes(upgrade_info_.md5_hash);
        body_data["firmware_version"] = PackString(upgrade_info_.firmware_version, 32);
        // 目录来自数据库：从storage_path/ftp_dir中截取主机后的目录
        std::string db_path = !upgrade_info_.storage_path.empty() ? upgrade_info_.storage_path : upgrade_info_.ftp_dir;
        std::string dir = ExtractDirAfterHost(db_path);
        std::string ftp_path = ftp_config_.host + ":" + std::to_string(ftp_config_.port) + dir;
        // 组装 username\tpassword\thost:port/<dir>/filename
        std::string ftp_payload = ftp_config_.user + '\t' + ftp_config_.password + '\t' + ftp_path + upgrade_info_.firmware_name;
        body_data["firmware_url_length"] = PackValue(static_cast<uint16_t>(ftp_payload.length()), 2);
        body_data["firmware_url"] = PackString(ftp_payload, ftp_payload.length());
    }
    
    // 从请求消息中获取协议ID，如果没有则使用默认值
    std::string protocol_id = request_msg.protocol_id.empty() ? "dp_protocol_v1" : request_msg.protocol_id;
    
    BodyBuildContext ctx; ctx.seq_num = seq_num; ctx.result = has_upgrade ? 0x00 : 0x01;
    // 将非通用字段放入 extras，便于 JSON 使用 source 指定
    for (const auto& kv : body_data) { ctx.extras[kv.first] = kv.second; }
    std::vector<uint8_t> body = CreateBody(response_msg_id, body_data, protocol_id, &ctx);
    std::vector<uint8_t> header = CreateHeader(response_msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateUpgradePushMessage(const std::string& device_unique_id, uint16_t seq_num, const DPower::DB::DPowerUpgradeTask& upgrade_task, const ParserConfig::FtpConfig& ftp_config, const std::string& protocol_id) {
    uint16_t msg_id = 33030;
    
    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["module_type"] = PackValue(upgrade_task.module_type, 1);
    body_data["force_upgrade"] = PackValue(static_cast<uint8_t>(upgrade_task.force_upgrade), 1);
    body_data["upgrade_task_id"] = PackString(upgrade_task.task_code, 18);
    
    uint16_t start_time_val = 0xFFFF;
    uint16_t end_time_val = 0xFFFF;
    if (upgrade_task.time_arrange_start > 0.0f || upgrade_task.time_arrange_end < 23.59f) {
        start_time_val = static_cast<uint16_t>(upgrade_task.time_arrange_start * 100);
        end_time_val = static_cast<uint16_t>(upgrade_task.time_arrange_end * 100);
    }
    body_data["start_time"] = PackValue(start_time_val, 2);
    body_data["end_time"] = PackValue(end_time_val, 2);
    
    body_data["file_size"] = PackValue(static_cast<uint32_t>(upgrade_task.file_size), 4);
    body_data["firmware_name_length"] = PackValue(static_cast<uint8_t>(upgrade_task.firmware_name.length()), 1);
    body_data["firmware_name"] = PackString(upgrade_task.firmware_name, upgrade_task.firmware_name.length());
    body_data["firmware_md5"] = HexStringToBytes(upgrade_task.md5_hash);
    body_data["firmware_version"] = PackString(upgrade_task.firmware_version, 32);

    // 目录来自数据库：从storage_path/ftp_dir中截取主机后的目录
    std::string db_path = !upgrade_task.storage_path.empty() ? upgrade_task.storage_path : upgrade_task.ftp_dir;
    std::string dir = ExtractDirAfterHost(db_path);
    std::string ftp_path = ftp_config.host + ":" + std::to_string(ftp_config.port) + dir;
    // 组装 username\tpassword\thost:port/<dir>/filename
    std::string ftp_payload = ftp_config.user + '\t' + ftp_config.password + '\t' + ftp_path + upgrade_task.firmware_name;

    body_data["firmware_url_length"] = PackValue(static_cast<uint16_t>(ftp_payload.length()), 2);
    body_data["firmware_url"] = PackString(ftp_payload, ftp_payload.length());
    
    BodyBuildContext ctx; for (const auto& kv : body_data) { ctx.extras[kv.first] = kv.second; }
    std::vector<uint8_t> body = CreateBody(msg_id, body_data, protocol_id, &ctx);
    std::vector<uint8_t> header = CreateHeader(msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateParameterDownloadMessage(const std::string& device_unique_id, uint16_t seq_num, uint8_t param_count, const std::string& protocol_id) {
    uint16_t msg_id = 33032;
    std::map<std::string, std::vector<uint8_t>> body_data;
    body_data["param_count"] = PackValue(param_count, 1);
    BodyBuildContext ctx; for (const auto& kv : body_data) { ctx.extras[kv.first] = kv.second; }
    std::vector<uint8_t> body = CreateBody(msg_id, body_data, protocol_id, &ctx);
    std::vector<uint8_t> header = CreateHeader(msg_id, body.size(), device_unique_id, seq_num, protocol_id);
    std::vector<uint8_t> packet;
    packet.insert(packet.end(), header.begin(), header.end());
    packet.insert(packet.end(), body.begin(), body.end());
    return AddCRCAndTail(packet, protocol_id);
}

std::vector<uint8_t> ResponseGenerator::CreateAutoResponse(const UniversalParsedMessage& request_msg) {
    switch (request_msg.msg_id) {
        case 2: return CreateRegistrationResponse(request_msg, 0x00, {});
        case 3: return CreateLoginResponse(request_msg, 0x00, 0);
        case 4: return CreateHeartbeatResponse(request_msg, 0);
        case 5: return CreateUpgradeQueryResponse(request_msg, false);
        default: return CreateGenericResponse(request_msg, 0x00, "OK");
    }
}

void ResponseGenerator::SetHeartbeatParams(uint8_t heart_interval, uint8_t keep_connect) {
    heart_interval_ = heart_interval;
    keep_connect_ = keep_connect;
}

void ResponseGenerator::SetUpgradeInfo(const DPower::DB::DPowerUpgradeTask& upgrade_info) {
    upgrade_info_ = upgrade_info;
}

void ResponseGenerator::SetFtpConfig(const ParserConfig::FtpConfig& ftp_config) {
    ftp_config_ = ftp_config;
}

std::vector<uint8_t> ResponseGenerator::GetCurrentTimeBCD() const {
    auto now = std::chrono::system_clock::now();
    std::time_t time_t = std::chrono::system_clock::to_time_t(now);
    std::tm* tm = std::localtime(&time_t);
    std::vector<uint8_t> bcd_time(6);
    bcd_time[0] = ((tm->tm_year - 100) / 10 << 4) | ((tm->tm_year - 100) % 10);
    bcd_time[1] = ((tm->tm_mon + 1) / 10 << 4) | ((tm->tm_mon + 1) % 10);
    bcd_time[2] = (tm->tm_mday / 10 << 4) | (tm->tm_mday % 10);
    bcd_time[3] = (tm->tm_hour / 10 << 4) | (tm->tm_hour % 10);
    bcd_time[4] = (tm->tm_min / 10 << 4) | (tm->tm_min % 10);
    bcd_time[5] = (tm->tm_sec / 10 << 4) | (tm->tm_sec % 10);
    return bcd_time;
}

void ResponseGenerator::SetAuthGenerator(std::shared_ptr<DPower::Utils::DPowerAuthGenerator> generator) {
    auth_generator_ = std::move(generator);
}

void ResponseGenerator::SetAuthSecret(const std::string& secret) {
    auth_secret_ = secret;
}

std::vector<uint8_t> ResponseGenerator::GenerateAuthenticationCode(const std::string& device_unique_id) const {
    if (auth_generator_) {
        try {
            std::string b64 = auth_generator_->Generate(device_unique_id, auth_secret_);
            // 使用UniversalParser的Base64解码方法
            if (universal_parser_) {
                return universal_parser_->DecodeBase64(b64);
            }
        } catch (...) {}
    }
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256_CTX sha256;
    SHA256_Init(&sha256);
    std::string salted_id = device_unique_id + "_a_fixed_salt_string_for_fallback";
    SHA256_Update(&sha256, salted_id.c_str(), salted_id.size());
    SHA256_Final(hash, &sha256);
    return std::vector<uint8_t>(hash, hash + 16);
}

std::vector<uint8_t> ResponseGenerator::CreateHeader(uint16_t msg_id, uint16_t body_size, const std::string& device_unique_id, 
                                                     uint16_t seq_num, const std::string& protocol_id) const {
    // 获取协议配置
    auto protocol_config = protocol_manager_->GetProtocolConfig(protocol_id);
    if (protocol_config.empty()) {
        // 如果找不到协议配置，使用默认的dp_protocol_v1格式
        protocol_config = protocol_manager_->GetProtocolConfig("dp_protocol_v1");
    }
    
    // 获取头部大小
    int header_size = 34; // 默认值
    if (protocol_config.contains("header") && protocol_config["header"].contains("size")) {
        header_size = protocol_config["header"]["size"];
    }
    
    std::vector<uint8_t> header(header_size, 0);
    
    // 根据协议配置填充头部字段（优先 value/valueHex/source，缺失时回退到旧的特例逻辑）
    if (protocol_config.contains("header") && protocol_config["header"].contains("fields")) {
        const auto& fields = protocol_config["header"]["fields"];
        
        for (const auto& field : fields) {
            std::string field_name = field["name"];
            int offset = field["offset"];
            int size = field["size"];
            std::string data_type = field["dataType"];
            auto write_int = [&](uint64_t val){
                bool little = (data_type.find('<') != std::string::npos);
                for (int i = 0; i < size; ++i) {
                    int idx = little ? i : (size - 1 - i);
                    header[offset + idx] = static_cast<uint8_t>(val & 0xFF);
                    val >>= 8;
                }
            };

            bool handled = false;
            // 1) 常量值：value 或 valueHex
            if (field.contains("value")) {
                handled = true;
                if (field["value"].is_number_integer() || field["value"].is_number_unsigned()) {
                    uint64_t v = field["value"].get<uint64_t>();
                    write_int(v);
                } else if (field["value"].is_string()) {
                    std::string v = field["value"].get<std::string>();
                    std::string padded = v; padded.resize(size, 0);
                    std::copy(padded.begin(), padded.begin() + size, header.begin() + offset);
                }
            } else if (field.contains("valueHex") && field["valueHex"].is_string()) {
                handled = true;
                std::string hex = field["valueHex"].get<std::string>();
                std::vector<uint8_t> bytes; bytes.reserve(size);
                for (size_t i = 0; i + 1 < hex.size() && bytes.size() < static_cast<size_t>(size); i += 2) {
                    uint8_t b = static_cast<uint8_t>(std::stoul(hex.substr(i, 2), nullptr, 16));
                    bytes.push_back(b);
                }
                // 写入，高位在前（按字段定义尺寸直接复制）
                for (int i = 0; i < size && i < static_cast<int>(bytes.size()); ++i) {
                    header[offset + i] = bytes[i];
                }
            }

            // 2) 来源：source（body_length/msg_id/device_id/seq_num）
            if (!handled && field.contains("source") && field["source"].is_string()) {
                handled = true;
                std::string src = field["source"].get<std::string>();
                if (src == "body_length") {
                    write_int(body_size);
                } else if (src == "msg_id") {
                    write_int(msg_id);
                } else if (src == "device_id") {
                    std::string padded_id = device_unique_id; padded_id.resize(size, 0);
                    std::copy(padded_id.begin(), padded_id.begin() + size, header.begin() + offset);
                } else if (src == "seq_num") {
                    write_int(seq_num);
                } else {
                    handled = false; // 未识别的来源，交给回退逻辑
                }
            }

            // 3) 回退：兼容旧的 dp 协议特例
            if (!handled) {
                if (field_name == "msg_head") {
                    if (protocol_id == "dp_protocol_v1" || protocol_id == "dp_protocol_v2") {
                        // 默认 0x5555...
                        header[offset] = 0x55; if (size > 1) header[offset + 1] = 0x55;
                        if (size > 2) header[offset + 2] = 0x55;
                        if (size > 3) header[offset + 3] = 0x55;
                    }
                } else if (field_name == "msg_type") {
                    if (protocol_id == "dp_protocol_v1" || protocol_id == "dp_protocol_v2") {
                        header[offset] = 0x03;
                    }
                } else if (field_name == "msg_body_len") {
                    write_int(body_size);
                } else if (field_name == "msg_id") {
                    write_int(msg_id);
                } else if (field_name == "devUniqueId") {
                    std::string padded_id = device_unique_id; padded_id.resize(size, 0);
                    std::copy(padded_id.begin(), padded_id.begin() + size, header.begin() + offset);
                } else if (field_name == "seNum") {
                    write_int(seq_num);
                }
            }
        }
    }
    
    return header;
}

std::vector<uint8_t> ResponseGenerator::CreateBody(uint16_t msg_id, const std::map<std::string, std::vector<uint8_t>>& body_data,
                                                   const std::string& protocol_id, const BodyBuildContext* ctx) const {
    std::vector<uint8_t> body;
    
    // 获取协议配置
    auto protocol_config = protocol_manager_->GetProtocolConfig(protocol_id);
    if (protocol_config.empty()) {
        // 如果找不到协议配置，使用默认的dp_protocol_v1格式
        protocol_config = protocol_manager_->GetProtocolConfig("dp_protocol_v1");
    }
    
    // 根据协议配置生成消息体
    if (protocol_config.contains("messages") && protocol_config["messages"].contains("bodies")) {
        const auto& bodies = protocol_config["messages"]["bodies"];
        std::string msg_id_str = std::to_string(msg_id);
        
        if (bodies.contains(msg_id_str)) {
            const auto& fields = bodies[msg_id_str];
            
            auto append_vec = [&](const std::vector<uint8_t>& v){ body.insert(body.end(), v.begin(), v.end()); };
            auto pack_val = [&](uint32_t v, size_t sz){ return PackValue(v, sz); };
            for (const auto& field : fields) {
                std::string field_name = field["name"];
                std::string data_type = field["dataType"];

                // 0) 调用方显式提供的 body_data 优先
                auto it = body_data.find(field_name);
                if (it != body_data.end()) { append_vec(it->second); continue; }

                // 1) value/valueHex/source（body）
                bool handled = false;
                if (field.contains("value")) {
                    handled = true;
                    if (field["value"].is_number_integer() || field["value"].is_number_unsigned()) {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 1;
                        append_vec(pack_val(field["value"].get<uint32_t>(), sz));
                    } else if (field["value"].is_string()) {
                        std::string s = field["value"].get<std::string>();
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : s.size();
                        append_vec(PackString(s, sz));
                    }
                } else if (field.contains("valueHex") && field["valueHex"].is_string()) {
                    handled = true;
                    std::string hex = field["valueHex"].get<std::string>();
                    std::vector<uint8_t> bytes; bytes.reserve(hex.size()/2);
                    for (size_t i = 0; i + 1 < hex.size(); i += 2) {
                        bytes.push_back(static_cast<uint8_t>(std::stoul(hex.substr(i,2), nullptr, 16)));
                    }
                    append_vec(bytes);
                } else if (field.contains("source") && field["source"].is_string() && ctx) {
                    handled = true;
                    std::string src = field["source"].get<std::string>();
                    if (src == "seq_num") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 2;
                        append_vec(pack_val(ctx->seq_num, sz));
                    } else if (src == "response_msg_id") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 2;
                        append_vec(pack_val(ctx->response_msg_id, sz));
                    } else if (src == "result") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 1;
                        append_vec(pack_val(ctx->result, sz));
                    } else if (src == "server_time_bcd") {
                        append_vec(ctx->server_time_bcd);
                    } else if (src == "heart_interval") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 1;
                        append_vec(pack_val(ctx->heart_interval, sz));
                    } else if (src == "keep_connect") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 1;
                        append_vec(pack_val(ctx->keep_connect, sz));
                    } else if (src == "authentication_code") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : ctx->authentication_code.size();
                        std::vector<uint8_t> tmp = ctx->authentication_code; tmp.resize(sz, 0); append_vec(tmp);
                    } else if (src == "additional_msg_length") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : 1;
                        append_vec(pack_val(static_cast<uint32_t>(ctx->additional_msg.size()), sz));
                    } else if (src == "additional_msg") {
                        size_t sz = field["size"].is_number_integer() ? static_cast<size_t>(field["size"].get<int>()) : ctx->additional_msg.size();
                        append_vec(PackString(ctx->additional_msg, sz));
                    } else {
                        // 若 source 指向 extras 的键
                        auto ex = ctx->extras.find(src);
                        if (ex != ctx->extras.end()) { append_vec(ex->second); }
                        else { handled = false; }
                    }
                }

                if (handled) continue;

                // 2) size 引用推断或 0 填充（兼容旧逻辑）
                int size = 0;
                try {
                    if (field["size"].is_number_integer()) {
                        size = field["size"].get<int>();
                    } else if (field["size"].is_string()) {
                        std::string ref = field["size"].get<std::string>();
                        auto ref_it = body_data.find(ref);
                        if (ref_it != body_data.end()) size = static_cast<int>(ref_it->second.size());
                    }
                } catch (...) { size = 0; }
                if (size > 0) body.insert(body.end(), static_cast<size_t>(size), 0);
            }
        } else {
            // 如果协议配置中没有对应的消息ID，使用默认的硬编码方式
            switch (msg_id) {
                case 32769: // 平台通用应答
                    if (body_data.count("response_seNum")) body.insert(body.end(), body_data.at("response_seNum").begin(), body_data.at("response_seNum").end());
                    if (body_data.count("response_msg_id")) body.insert(body.end(), body_data.at("response_msg_id").begin(), body_data.at("response_msg_id").end());
                    if (body_data.count("result")) body.insert(body.end(), body_data.at("result").begin(), body_data.at("result").end());
                    if (body_data.count("additional_msg_length")) body.insert(body.end(), body_data.at("additional_msg_length").begin(), body_data.at("additional_msg_length").end());
                    if (body_data.count("additional_msg")) body.insert(body.end(), body_data.at("additional_msg").begin(), body_data.at("additional_msg").end());
                    break;
                case 32770: // 终端注册应答
                    if (body_data.count("response_seNum")) body.insert(body.end(), body_data.at("response_seNum").begin(), body_data.at("response_seNum").end());
                    if (body_data.count("result")) body.insert(body.end(), body_data.at("result").begin(), body_data.at("result").end());
                    if (body_data.count("authentication_code")) {
                        auto& auth_vec = body_data.at("authentication_code");
                        body.insert(body.end(), auth_vec.begin(), auth_vec.end());
                        
                        // 调试：打印实际插入到响应体中的鉴权码
                        std::ostringstream oss;
                        oss << std::hex << std::setfill('0');
                        for (auto b : auth_vec) {
                            oss << std::setw(2) << static_cast<int>(b);
                        }
                        try {
                            std::cout << "[DEBUG] [ResponseGenerator] Auth code inserted into response body: " << oss.str() << std::endl;
                        } catch (...) {}
                    }
                    break;
                case 32771: // 终端鉴权应答
                    if (body_data.count("response_seNum")) body.insert(body.end(), body_data.at("response_seNum").begin(), body_data.at("response_seNum").end());
                    if (body_data.count("result")) body.insert(body.end(), body_data.at("result").begin(), body_data.at("result").end());
                    if (body_data.count("server_time")) body.insert(body.end(), body_data.at("server_time").begin(), body_data.at("server_time").end());
                    if (body_data.count("heart_interval")) body.insert(body.end(), body_data.at("heart_interval").begin(), body_data.at("heart_interval").end());
                    if (body_data.count("keep_connect")) body.insert(body.end(), body_data.at("keep_connect").begin(), body_data.at("keep_connect").end());
                    break;
                case 32772: // 心跳应答
                    if (body_data.count("response_seNum")) body.insert(body.end(), body_data.at("response_seNum").begin(), body_data.at("response_seNum").end());
                    if (body_data.count("keep_connect")) body.insert(body.end(), body_data.at("keep_connect").begin(), body_data.at("keep_connect").end());
                    break;
                case 32773: // 查询固件版本应答
                    if (body_data.count("response_seNum")) body.insert(body.end(), body_data.at("response_seNum").begin(), body_data.at("response_seNum").end());
                    if (body_data.count("result")) body.insert(body.end(), body_data.at("result").begin(), body_data.at("result").end());
                    if (body_data.count("force_upgrade")) body.insert(body.end(), body_data.at("force_upgrade").begin(), body_data.at("force_upgrade").end());
                    if (body_data.count("upgrade_task_id")) body.insert(body.end(), body_data.at("upgrade_task_id").begin(), body_data.at("upgrade_task_id").end());
                    if (body_data.count("start_time")) body.insert(body.end(), body_data.at("start_time").begin(), body_data.at("start_time").end());
                    if (body_data.count("end_time")) body.insert(body.end(), body_data.at("end_time").begin(), body_data.at("end_time").end());
                    if (body_data.count("module_type")) body.insert(body.end(), body_data.at("module_type").begin(), body_data.at("module_type").end());
                    if (body_data.count("file_size")) body.insert(body.end(), body_data.at("file_size").begin(), body_data.at("file_size").end());
                    if (body_data.count("firmware_name_length")) body.insert(body.end(), body_data.at("firmware_name_length").begin(), body_data.at("firmware_name_length").end());
                    if (body_data.count("firmware_name")) body.insert(body.end(), body_data.at("firmware_name").begin(), body_data.at("firmware_name").end());
                    if (body_data.count("firmware_md5")) body.insert(body.end(), body_data.at("firmware_md5").begin(), body_data.at("firmware_md5").end());
                    if (body_data.count("firmware_version")) body.insert(body.end(), body_data.at("firmware_version").begin(), body_data.at("firmware_version").end());
                    if (body_data.count("firmware_url_length")) body.insert(body.end(), body_data.at("firmware_url_length").begin(), body_data.at("firmware_url_length").end());
                    if (body_data.count("firmware_url")) body.insert(body.end(), body_data.at("firmware_url").begin(), body_data.at("firmware_url").end());
                    break;
                case 33030: // 通知终端升级
                    if (body_data.count("module_type")) body.insert(body.end(), body_data.at("module_type").begin(), body_data.at("module_type").end());
                    if (body_data.count("force_upgrade")) body.insert(body.end(), body_data.at("force_upgrade").begin(), body_data.at("force_upgrade").end());
                    if (body_data.count("upgrade_task_id")) body.insert(body.end(), body_data.at("upgrade_task_id").begin(), body_data.at("upgrade_task_id").end());
                    if (body_data.count("start_time")) body.insert(body.end(), body_data.at("start_time").begin(), body_data.at("start_time").end());
                    if (body_data.count("end_time")) body.insert(body.end(), body_data.at("end_time").begin(), body_data.at("end_time").end());
                    if (body_data.count("file_size")) body.insert(body.end(), body_data.at("file_size").begin(), body_data.at("file_size").end());
                    if (body_data.count("firmware_name_length")) body.insert(body.end(), body_data.at("firmware_name_length").begin(), body_data.at("firmware_name_length").end());
                    if (body_data.count("firmware_name")) body.insert(body.end(), body_data.at("firmware_name").begin(), body_data.at("firmware_name").end());
                    if (body_data.count("firmware_md5")) body.insert(body.end(), body_data.at("firmware_md5").begin(), body_data.at("firmware_md5").end());
                    if (body_data.count("firmware_version")) body.insert(body.end(), body_data.at("firmware_version").begin(), body_data.at("firmware_version").end());
                    if (body_data.count("firmware_url_length")) body.insert(body.end(), body_data.at("firmware_url_length").begin(), body_data.at("firmware_url_length").end());
                    if (body_data.count("firmware_url")) body.insert(body.end(), body_data.at("firmware_url").begin(), body_data.at("firmware_url").end());
                    break;
                default:
                    for (const auto& field : body_data) {
                        body.insert(body.end(), field.second.begin(), field.second.end());
                    }
                    break;
            }
        }
    } else {
        // 如果协议配置中没有消息体定义，使用默认的硬编码方式
        for (const auto& field : body_data) {
            body.insert(body.end(), field.second.begin(), field.second.end());
        }
    }
    
    return body;
}

std::vector<uint8_t> ResponseGenerator::AddCRCAndTail(const std::vector<uint8_t>& packet, const std::string& protocol_id) const {
    std::vector<uint8_t> complete_packet = packet;
    
    // 获取协议解析策略
    auto strategy = universal_parser_->GetProtocolStrategy(protocol_id);
    if (strategy.has_value()) {
        const auto& protocol_strategy = strategy.value();
        
        // 添加CRC校验
        if (protocol_strategy.has_crc) {
            uint16_t crc = universal_parser_->CalculateCRC16(packet.data(), packet.size());
            
            if (protocol_strategy.crc_endianness == "little") {
                complete_packet.push_back(static_cast<uint8_t>(crc & 0xFF));
                complete_packet.push_back(static_cast<uint8_t>((crc >> 8) & 0xFF));
            } else {
                complete_packet.push_back(static_cast<uint8_t>((crc >> 8) & 0xFF));
                complete_packet.push_back(static_cast<uint8_t>(crc & 0xFF));
            }
        }
        
        // 添加尾部签名
        if (!protocol_strategy.tail_signature.empty()) {
            complete_packet.insert(complete_packet.end(), 
                                 protocol_strategy.tail_signature.begin(), 
                                 protocol_strategy.tail_signature.end());
        }
    } else {
        // 如果找不到协议策略，使用默认的dp_protocol_v1格式
        uint16_t crc = universal_parser_->CalculateCRC16(packet.data(), packet.size());
        complete_packet.push_back(static_cast<uint8_t>(crc & 0xFF));
        complete_packet.push_back(static_cast<uint8_t>((crc >> 8) & 0xFF));
        complete_packet.push_back(0xAA);
        complete_packet.push_back(0xAA);
    }
    
    return complete_packet;
}

std::vector<uint8_t> ResponseGenerator::PackString(const std::string& str, size_t size) const {
    std::vector<uint8_t> result(size, 0);
    size_t copy_size = std::min(str.size(), size);
    std::copy(str.begin(), str.begin() + copy_size, result.begin());
    return result;
}

std::string ResponseGenerator::ExtractDeviceUniqueId(const UniversalParsedMessage& msg) const {
    return msg.GetField<std::string>("devUniqueId");
}

uint16_t ResponseGenerator::ExtractSequenceNumber(const UniversalParsedMessage& msg) const {
    return msg.GetField<uint16_t>("seNum");
}

std::string ResponseGenerator::Base64Encode(const std::vector<uint8_t>& data) const {
    // 使用UniversalParser的Base64Encode方法
    if (universal_parser_) {
        return universal_parser_->Base64Encode(data);
    } else {
        // 如果没有universal_parser_，使用本地Base64编码
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
}

std::vector<uint8_t> ResponseGenerator::PackValue(uint32_t value, size_t size) const {
    std::vector<uint8_t> result(size);
    for (size_t i = 0; i < size; ++i) {
        result[i] = static_cast<uint8_t>(value & 0xFF);
        value >>= 8;
    }
    return result;
}

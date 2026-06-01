#include "logic/services/DeviceServiceImpl.h"
#include "logic/utils/MessageUtils.h"
#include "dpower/utils/Auth.h"
#include "logic/utils/Logger.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <thread>
#include <random>
#include <algorithm>

// 万能获取：优先使用主字段名，取不到则回退别名
template <typename T>
static T GetFieldAlias(const UniversalParsedMessage &msg,
                       const std::string &primary,
                       const std::string &alias,
                       const T &defVal)
{
    if (msg.HasField(primary))
        return msg.GetField<T>(primary, defVal);
    if (msg.HasField(alias))
        return msg.GetField<T>(alias, defVal);
    return defVal;
}

static std::string ToHex(const std::string &s)
{
    std::ostringstream oss;
    oss << "0x";
    for (unsigned char c : s)
    {
        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
    }
    return oss.str();
}

// 简单Base64解码（与解析器保持一致的字符表）
static std::vector<uint8_t> DecodeBase64Local(const std::string &base64_data)
{
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789+/";
    std::vector<uint8_t> result;
    int val = 0, valb = -8;
    for (char c : base64_data)
    {
        if (c == '=')
            break;
        auto it = std::find(base64_chars.begin(), base64_chars.end(), c);
        if (it == base64_chars.end())
            continue;
        val = (val << 6) | static_cast<int>(it - base64_chars.begin());
        valb += 6;
        if (valb >= 0)
        {
            result.push_back(static_cast<uint8_t>((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return result;
}

// 针对 dp_protocol_v1 注册报文（msg_id=2）的三段变长字段提取（带边界保护）
static void ExtractDpV1RegVarFields(const std::string &raw_base64,
                                    std::string &out_hw,
                                    std::string &out_main,
                                    std::string &out_currency)
{
    out_hw.clear();
    out_main.clear();
    out_currency.clear();
    const auto raw = DecodeBase64Local(raw_base64);
    if (raw.size() < 34 /*header*/ + 16 + 1)
        return;
    const size_t header = 34;
    size_t pos = header;
    auto safe_slice = [&](size_t start, size_t count) -> std::string
    {
        if (start >= raw.size())
            return std::string();
        size_t end_guard = raw.size() >= 4 ? raw.size() - 4 : raw.size(); // 预留CRC(2)+尾(2)
        size_t max_count = (start + count > end_guard) ? (end_guard - start) : count;
        if (start >= end_guard || max_count == 0)
            return std::string();
        return std::string(reinterpret_cast<const char *>(&raw[start]), max_count);
    };
    auto rd_u8 = [&](size_t off) -> uint8_t
    { return off < raw.size() ? raw[off] : 0; };
    auto rd_u16le = [&](size_t off) -> uint16_t
    {
        if (off + 1 >= raw.size())
            return 0;
        return static_cast<uint16_t>(raw[off]) | (static_cast<uint16_t>(raw[off + 1]) << 8);
    };

    // 固定区
    // manufacturer(16)
    pos += 16;
    // branchInfoLength(1)
    if (pos >= raw.size())
        return;
    uint8_t branch_len = rd_u8(pos);
    pos += 1;
    // branchInfo(N)
    pos += branch_len;
    // deviceType(1), deviceModel(16), suffixFlag(8), firmwareVersion(32)
    pos += 1 + 16 + 8 + 32;
    if (pos >= raw.size())
        return;

    // hardwareVersionLength(1) + hardwareVersion(N)
    uint8_t hw_len = rd_u8(pos);
    pos += 1;
    out_hw = safe_slice(pos, hw_len);
    pos += hw_len;

    // mainSoftwareVersionLength(2) + mainSoftwareVersion(N)
    uint16_t main_len = rd_u16le(pos);
    pos += 2;
    out_main = safe_slice(pos, main_len);
    pos += main_len;

    // currencyDbVersionLength(2) + currencyDbVersion(N)
    uint16_t curr_len = rd_u16le(pos);
    pos += 2;
    out_currency = safe_slice(pos, curr_len);
}

// 规范化设备ID：去掉报文中的填充字节和首尾空格，避免 DB 精确匹配失败
static std::string NormalizeDeviceId(std::string s)
{
    // 去掉尾部填充字节：0x00, 0xFF, 空格
    while (!s.empty())
    {
        unsigned char b = static_cast<unsigned char>(s.back());
        if (b == 0x00 || b == 0xFF || b == 0x20 || b == '\r' || b == '\n' || b == '\t')
        {
            s.pop_back();
        }
        else
        {
            break;
        }
    }
    // 去掉首部空白字符
    size_t start = 0;
    while (start < s.size())
    {
        unsigned char b = static_cast<unsigned char>(s[start]);
        if (b == 0x20 || b == '\r' || b == '\n' || b == '\t')
        {
            ++start;
        }
        else
        {
            break;
        }
    }
    if (start > 0)
        s.erase(0, start);
    return s;
}

DeviceServiceImpl::DeviceServiceImpl(
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
    std::shared_ptr<ResponseGenerator> response_generator,
    const ParserConfig::FtpConfig &ftp_config,
    const ParserConfig::AuthConfig &auth_config)
    : db_client_(std::move(db_client)),
      cache_client_(std::move(cache_client)),
      mq_client_(std::move(mq_client)),
      response_generator_(std::move(response_generator)),
      ftp_config_(ftp_config),
      auth_config_(auth_config)
{
    if (!db_client_)
    {
        throw std::invalid_argument("Database client cannot be null");
    }
    if (!cache_client_)
    {
        throw std::invalid_argument("Cache client cannot be null");
    }
    if (!mq_client_)
    {
        throw std::invalid_argument("Message queue client cannot be null");
    }
    if (!response_generator_)
    {
        throw std::invalid_argument("Response generator cannot be null");
    }
}

DeviceServiceImpl::~DeviceServiceImpl()
{
    StopOfflineDetection();
}

RegistrationResult DeviceServiceImpl::RegisterDevice(const UniversalParsedMessage &parsed_msg)
{
    const std::string raw_device_id = parsed_msg.GetField<std::string>("devUniqueId");
    const std::string device_id = NormalizeDeviceId(raw_device_id);
    const std::string device_model = parsed_msg.GetField<std::string>("deviceModel");

    if (raw_device_id != device_id)
    {
        Log("DEBUG", "Normalized device_id from ['" + raw_device_id + "'] to ['" + device_id + "']");
    }

    Log("INFO", "Processing registration request from device: " + device_id);

    // 协议与数据库连接检查
    if (device_id.empty() || device_model.empty())
    {
        Log("WARN", "Protocol error: missing device_id or device_model");
        // 0xFE - 协议异常
        return {false, "Protocol error", {}, 0xFE};
    }
    if (!db_client_ || !db_client_->IsConnected())
    {
        Log("ERROR", "Database client not available");
        // 0xFF - 系统异常
        return {false, "Database not available", {}, 0xFF};
    }

    using namespace DPower::DB;

    // 1. 首先查询缓存
    auto cached_record_opt = cache_client_->GetDevice(device_id);
    if (cached_record_opt)
    {
        Log("DEBUG", "Cache hit for device record: " + device_id);
        DPowerDeviceRecord &record = *cached_record_opt;

        if (!record.model_name.empty() && record.model_name != device_model)
        {
            Log("WARN", "Device model mismatch (from cache). expected=" + record.model_name + ", got=" + device_model);
            return {false, "Device model mismatch", {}, 0x03};
        }
        if (!record.auth_code.empty())
        {
            Log("INFO", "Device already registered (from cache): " + device_id);

            // 即使设备已注册，也要更新设备信息
            DPowerDeviceRecord update_rec = record;
            // 兼容 camelCase/snake_case
            update_rec.device_type = GetFieldAlias<uint8_t>(parsed_msg, "deviceType", "device_type", record.device_type);

            // 获取原始字段值
            std::string firmware_version = GetFieldAlias<std::string>(parsed_msg, "firmwareVersion", "firmware_version", record.firmware_version);
            std::string hardware_version = GetFieldAlias<std::string>(parsed_msg, "hardwareVersion", "hardware_version", record.hardware_version);
            std::string suffix_marker = GetFieldAlias<std::string>(parsed_msg, "suffixFlag", "suffix_marker", record.suffix_marker);
            std::string currency_library_version = GetFieldAlias<std::string>(parsed_msg, "currencyDbVersion", "currency_library_version", record.currency_library_version);
            std::string main_software_version = GetFieldAlias<std::string>(parsed_msg, "mainSoftwareVersion", "main_software_version", record.main_software_version);

            // 兼容：读取长度字段（用于必要的健壮回退判断）
            uint8_t hw_len = GetFieldAlias<uint8_t>(parsed_msg, "hardwareVersionLength", "hardware_version_length", 0);
            uint16_t main_len = GetFieldAlias<uint16_t>(parsed_msg, "mainSoftwareVersionLength", "main_software_version_length", 0);
            uint16_t curr_len = GetFieldAlias<uint16_t>(parsed_msg, "currencyDbVersionLength", "currency_db_version_length", 0);

            // 当长度异常时，进行回退解析（直接从raw按协议顺序提取，避免错位）
            bool need_fallback = (main_len == 0 || main_len > 1024 || curr_len == 0);
            if (need_fallback)
            {
                std::string fhw, fmain, fcurr;
                ExtractDpV1RegVarFields(parsed_msg.raw_data_base64, fhw, fmain, fcurr);
                if (!fhw.empty())
                    hardware_version = fhw;
                if (!fmain.empty())
                    main_software_version = fmain;
                if (!fcurr.empty())
                    currency_library_version = fcurr;
            }

            // 检查并处理填充值，如果字段全是无效字符则设为空，否则进行清理
            if (IsAllPaddingChars(firmware_version))
            {
                update_rec.firmware_version = "";
            }
            else
            {
                update_rec.firmware_version = MessageUtils::CleanString(firmware_version);
            }

            if (IsAllPaddingChars(hardware_version))
            {
                update_rec.hardware_version = "";
            }
            else
            {
                update_rec.hardware_version = MessageUtils::CleanString(hardware_version);
            }

            if (IsAllPaddingChars(suffix_marker))
            {
                update_rec.suffix_marker = "";
            }
            else
            {
                update_rec.suffix_marker = MessageUtils::CleanString(suffix_marker);
            }

            if (IsAllPaddingChars(currency_library_version))
            {
                update_rec.currency_library_version = "";
            }
            else
            {
                update_rec.currency_library_version = MessageUtils::CleanString(currency_library_version);
            }

            if (IsAllPaddingChars(main_software_version))
            {
                update_rec.main_software_version = "";
            }
            else
            {
                update_rec.main_software_version = MessageUtils::CleanString(main_software_version);
            }

            // 记录将要写入的字段值，便于排查
            Log("DEBUG", "UpdateDevice payload (already-registered): type=" + std::to_string(update_rec.device_type) + ", fw='" + update_rec.firmware_version + "', hw='" + update_rec.hardware_version + "', suffix='" + update_rec.suffix_marker + "', currency='" + update_rec.currency_library_version + "', main='" + update_rec.main_software_version + "'");

            // 更新数据库
            auto update_res = db_client_->UpdateDevice(update_rec);
            if (update_res.success)
            {
                Log("DEBUG", "Updated device info for already registered device: " + device_id);
                // 更新缓存（防御性 try/catch，避免 JSON UTF-8 导致流程中断）
                try
                {
                    cache_client_->SetDevice(update_rec, 3600);
                }
                catch (const std::exception &e)
                {
                    Log("WARN", std::string("Cache SetDevice failed (cache path): ") + e.what());
                }
            }
            else
            {
                Log("WARN", "Failed to update device info for already registered device: " + device_id + " - " + update_res.error_message);
            }

            // 安全解析缓存记录中的鉴权码：支持HEX字符串或原始字节串，输出稳定的16字节
            auto hex_nibble = [](char c) -> int
            {
                if (c >= '0' && c <= '9')
                    return c - '0';
                if (c >= 'a' && c <= 'f')
                    return 10 + (c - 'a');
                if (c >= 'A' && c <= 'F')
                    return 10 + (c - 'A');
                return -1;
            };
            auto parse_auth = [&](const std::string &s) -> std::vector<uint8_t>
            {
                std::vector<uint8_t> out;
                if (s.empty())
                    return out;
                bool is_hex = (s.size() % 2 == 0);
                if (is_hex)
                {
                    for (size_t i = 0; i < s.size(); i += 2)
                    {
                        int hi = hex_nibble(s[i]);
                        int lo = hex_nibble(s[i + 1]);
                        if (hi < 0 || lo < 0)
                        {
                            is_hex = false;
                            break;
                        }
                        out.push_back(static_cast<uint8_t>((hi << 4) | lo));
                    }
                }
                if (!is_hex)
                {
                    // 当不是合法HEX时，按原始字节使用
                    out.assign(s.begin(), s.end());
                }
                // 规范为16字节：截断或补零
                if (out.size() > 16)
                    out.resize(16);
                while (out.size() < 16)
                    out.push_back(0);
                return out;
            };
            std::vector<uint8_t> code_vec = parse_auth(record.auth_code);
            // 临时修改：返回 0x00 让设备端认为这是成功的注册
            // 原来是：0x01 - 已经注册（返回现有鉴权码）
            return {true, "Device already registered", code_vec, 0x00};
        }
    }

    // 2. 缓存未命中，查询数据库
    Log("DEBUG", "Cache miss for device record: " + device_id + ". Querying database...");
    DPowerDeviceRecord db_record;

    try
    {
        auto db_res = db_client_->GetDeviceById(device_id, db_record);
        bool device_exists_in_db = (db_res.success && !db_record.device_id.empty());

        if (!db_res.success)
        {
            Log("ERROR", "Database query failed for device: " + device_id + ", error: " + db_res.error_message);
            return {false, "Database query failed", {}, 0xFF};
        }

        if (device_exists_in_db)
        {
            Log("DEBUG", "Database hit for device record: " + device_id);

            // 型号必须存在且匹配
            if (db_record.model_name.empty())
            {
                Log("WARN", "Device model not set in database for device: " + device_id + ", blocking registration.");
                return {false, "Device model missing in DB", {}, 0x03};
            }
            if (db_record.model_name != device_model)
            {
                Log("WARN", "Device model mismatch (from database). expected=" + db_record.model_name + ", got=" + device_model);
                return {false, "Device model mismatch", {}, 0x03};
            }
            if (!db_record.auth_code.empty())
            {
                Log("INFO", "Device already registered (from database): " + device_id);
                Log("DEBUG", "DB auth_code not empty, length=" + std::to_string(db_record.auth_code.length()) + ", value=" + db_record.auth_code);

                // 即使设备已注册，也要更新设备信息
                DPowerDeviceRecord update_rec = db_record;
                // 兼容 camelCase/snake_case
                update_rec.device_type = GetFieldAlias<uint8_t>(parsed_msg, "deviceType", "device_type", db_record.device_type);

                // 获取原始字段值
                std::string firmware_version = GetFieldAlias<std::string>(parsed_msg, "firmwareVersion", "firmware_version", db_record.firmware_version);
                std::string hardware_version = GetFieldAlias<std::string>(parsed_msg, "hardwareVersion", "hardware_version", db_record.hardware_version);
                std::string suffix_marker = GetFieldAlias<std::string>(parsed_msg, "suffixFlag", "suffix_marker", db_record.suffix_marker);
                std::string currency_library_version = GetFieldAlias<std::string>(parsed_msg, "currencyDbVersion", "currency_library_version", db_record.currency_library_version);
                std::string main_software_version = GetFieldAlias<std::string>(parsed_msg, "mainSoftwareVersion", "main_software_version", db_record.main_software_version);

                // 兼容：读取长度字段（用于必要的健壮回退判断）
                uint8_t hw_len2 = GetFieldAlias<uint8_t>(parsed_msg, "hardwareVersionLength", "hardware_version_length", 0);
                uint16_t main_len2 = GetFieldAlias<uint16_t>(parsed_msg, "mainSoftwareVersionLength", "main_software_version_length", 0);
                uint16_t curr_len2 = GetFieldAlias<uint16_t>(parsed_msg, "currencyDbVersionLength", "currency_db_version_length", 0);

                // 当长度异常时，进行回退解析（直接从raw按协议顺序提取，避免错位）
                bool need_fallback2 = (main_len2 == 0 || main_len2 > 1024 || curr_len2 == 0);
                if (need_fallback2)
                {
                    std::string fhw, fmain, fcurr;
                    ExtractDpV1RegVarFields(parsed_msg.raw_data_base64, fhw, fmain, fcurr);
                    if (!fhw.empty())
                        hardware_version = fhw;
                    if (!fmain.empty())
                        main_software_version = fmain;
                    if (!fcurr.empty())
                        currency_library_version = fcurr;
                }

                // 检查并处理填充值，如果字段全是无效字符则设为空，否则进行清理
                if (IsAllPaddingChars(firmware_version))
                {
                    update_rec.firmware_version = "";
                }
                else
                {
                    update_rec.firmware_version = MessageUtils::CleanString(firmware_version);
                }

                if (IsAllPaddingChars(hardware_version))
                {
                    update_rec.hardware_version = "";
                }
                else
                {
                    update_rec.hardware_version = MessageUtils::CleanString(hardware_version);
                }

                if (IsAllPaddingChars(suffix_marker))
                {
                    update_rec.suffix_marker = "";
                }
                else
                {
                    update_rec.suffix_marker = MessageUtils::CleanString(suffix_marker);
                }

                if (IsAllPaddingChars(currency_library_version))
                {
                    update_rec.currency_library_version = "";
                }
                else
                {
                    update_rec.currency_library_version = MessageUtils::CleanString(currency_library_version);
                }

                if (IsAllPaddingChars(main_software_version))
                {
                    update_rec.main_software_version = "";
                }
                else
                {
                    update_rec.main_software_version = MessageUtils::CleanString(main_software_version);
                }

                // 更新数据库
                auto update_res = db_client_->UpdateDevice(update_rec);
                if (update_res.success)
                {
                    Log("DEBUG", "Updated device info for already registered device: " + device_id);
                    // 更新缓存（防御性 try/catch）
                    try
                    {
                        cache_client_->SetDevice(update_rec, 3600);
                    }
                    catch (const std::exception &e)
                    {
                        Log("WARN", std::string("Cache SetDevice failed (db path): ") + e.what());
                    }
                }
                else
                {
                    Log("WARN", "Failed to update device info for already registered device: " + device_id + " - " + update_res.error_message);
                    // 如果更新失败，仍然使用原始记录
                    try
                    {
                        cache_client_->SetDevice(db_record, 3600);
                    }
                    catch (const std::exception &e)
                    {
                        Log("WARN", std::string("Cache SetDevice failed (db fallback): ") + e.what());
                    }
                }

                // 安全解析数据库中的鉴权码
                auto hex_nibble2 = [](char c) -> int
                {
                    if (c >= '0' && c <= '9')
                        return c - '0';
                    if (c >= 'a' && c <= 'f')
                        return 10 + (c - 'a');
                    if (c >= 'A' && c <= 'F')
                        return 10 + (c - 'A');
                    return -1;
                };
                auto parse_auth2 = [&](const std::string &s) -> std::vector<uint8_t>
                {
                    std::vector<uint8_t> out;
                    if (s.empty())
                        return out;
                    bool is_hex = (s.size() % 2 == 0);
                    if (is_hex)
                    {
                        for (size_t i = 0; i < s.size(); i += 2)
                        {
                            int hi = hex_nibble2(s[i]);
                            int lo = hex_nibble2(s[i + 1]);
                            if (hi < 0 || lo < 0)
                            {
                                is_hex = false;
                                break;
                            }
                            out.push_back(static_cast<uint8_t>((hi << 4) | lo));
                        }
                    }
                    if (!is_hex)
                    {
                        out.assign(s.begin(), s.end());
                    }
                    if (out.size() > 16)
                        out.resize(16);
                    while (out.size() < 16)
                        out.push_back(0);
                    return out;
                };
                std::vector<uint8_t> code_vec;
                code_vec = parse_auth2(db_record.auth_code);
                return {true, "Device already registered", code_vec, 0x01};
            }
        }

        // 3. 设备未注册，进行注册（仅允许数据库已存在且型号匹配的设备）
        if (!device_exists_in_db)
        {
            Log("WARN", "Registration blocked: device not found in database: " + device_id);
            return {false, "Device not found", {}, 0x02};
        }
        Log("INFO", "Device found in DB and not registered yet, proceeding with registration: " + device_id);
        Log("DEBUG", "DB auth_code empty, length=" + std::to_string(db_record.auth_code.length()) + ", value=[" + db_record.auth_code + "]");
        // 使用DPower Auth算法生成鉴权码（Base64），随后解码为原始字节并取前16字节
        auto auth_factory = DPower::Utils::CreateOpenSSLAuthFactory();
        auto auth_generator = auth_factory->Create();

        // 生成Base64表示的鉴权码
        std::string auth_code_base64 = auth_generator->Generate(device_id, auth_config_.server_secret_key);

        // 解码为原始字节
        std::vector<uint8_t> auth_code_vec = DecodeBase64Local(auth_code_base64);
        if (auth_code_vec.empty())
        {
            // 解码失败时的保底策略：退化为对Base64字符串逐字节取值（与旧逻辑一致），并进行长度归一化
            Log("WARN", "DecodeBase64 failed for generated auth code, falling back to ASCII bytes");
            for (size_t i = 0; i < std::min(auth_code_base64.length(), size_t(16)); ++i)
            {
                auth_code_vec.push_back(static_cast<uint8_t>(auth_code_base64[i]));
            }
        }
        // 归一化为16字节：截断或补零
        if (auth_code_vec.size() > 16)
            auth_code_vec.resize(16);
        while (auth_code_vec.size() < 16)
            auth_code_vec.push_back(0);

        // 转十六进制字符串用于持久化与缓存
        std::ostringstream oss;
        oss << std::hex << std::setfill('0');
        for (auto b : auth_code_vec)
        {
            oss << std::setw(2) << static_cast<int>(b);
        }
        std::string auth_code_hex = oss.str();

        // 调试日志：同时打印Base64与标准化后的HEX
        Log("DEBUG", "Generated auth code - Base64(len=" + std::to_string(auth_code_base64.size()) + ") => HEX:" + auth_code_hex);

        // 创建设备记录
        DPowerDeviceRecord reg_rec;
        reg_rec.device_id = device_id;
        // 使用数据库中的型号（已校验与报文一致）
        reg_rec.model_name = db_record.model_name;
        reg_rec.auth_code = auth_code_hex;

        // 从注册报文中获取更多设备信息
        // 兼容 camelCase/snake_case
        reg_rec.device_type = GetFieldAlias<uint8_t>(parsed_msg, "deviceType", "device_type", 0);

        // 获取原始字段值
        std::string firmware_version = GetFieldAlias<std::string>(parsed_msg, "firmwareVersion", "firmware_version", "");
        std::string hardware_version = GetFieldAlias<std::string>(parsed_msg, "hardwareVersion", "hardware_version", "");
        std::string suffix_marker = GetFieldAlias<std::string>(parsed_msg, "suffixFlag", "suffix_marker", "");
        std::string currency_library_version = GetFieldAlias<std::string>(parsed_msg, "currencyDbVersion", "currency_library_version", "");
        std::string main_software_version = GetFieldAlias<std::string>(parsed_msg, "mainSoftwareVersion", "main_software_version", "");

        // 检查并处理填充值，如果字段全是无效字符则设为空，否则进行清理
        if (IsAllPaddingChars(firmware_version))
        {
            reg_rec.firmware_version = "";
        }
        else
        {
            reg_rec.firmware_version = MessageUtils::CleanString(firmware_version);
        }

        if (IsAllPaddingChars(hardware_version))
        {
            reg_rec.hardware_version = "";
        }
        else
        {
            reg_rec.hardware_version = MessageUtils::CleanString(hardware_version);
        }

        if (IsAllPaddingChars(suffix_marker))
        {
            reg_rec.suffix_marker = "";
        }
        else
        {
            reg_rec.suffix_marker = MessageUtils::CleanString(suffix_marker);
        }

        if (IsAllPaddingChars(currency_library_version))
        {
            reg_rec.currency_library_version = "";
        }
        else
        {
            reg_rec.currency_library_version = MessageUtils::CleanString(currency_library_version);
        }

        if (IsAllPaddingChars(main_software_version))
        {
            reg_rec.main_software_version = "";
        }
        else
        {
            reg_rec.main_software_version = MessageUtils::CleanString(main_software_version);
        }

        // 记录将要写入的字段值，便于排查
        Log("DEBUG", "UpdateDevice payload (register-new-or-existing): type=" + std::to_string(reg_rec.device_type) + ", fw='" + reg_rec.firmware_version + "', hw='" + reg_rec.hardware_version + "', suffix='" + reg_rec.suffix_marker + "', currency='" + reg_rec.currency_library_version + "', main='" + reg_rec.main_software_version + "'");

        auto update_res = db_client_->UpdateDevice(reg_rec);
        if (!update_res.success)
        {
            Log("ERROR", "Failed to UpdateDevice device info in database: " + update_res.error_message);
            // 0xFF - 系统异常
            return {false, "Database update failed", {}, 0xFF};
        }

        // 单独写入鉴权码，避免通用更新路径引发长度问题
        Log("DEBUG", "Attempting to save auth_code to database: device_id=" + device_id + ", auth_code_hex=" + auth_code_hex);
        auto auth_res = db_client_->UpdateDeviceAuthCode(device_id, auth_code_hex);
        if (!auth_res.success)
        {
            Log("ERROR", "Failed to persist authentication_code for device: " + device_id + ", error: " + auth_res.error_message);
            return {false, "Persist auth code failed", {}, 0xFF};
        }
        Log("DEBUG", "Successfully saved auth_code to database for device: " + device_id);

        // 更新数据库后，刷新缓存，包含鉴权码
        try
        {
            cache_client_->SetDevice(reg_rec, 3600);
        }
        catch (const std::exception &e)
        {
            Log("WARN", std::string("Cache SetDevice failed (register new): ") + e.what());
        }

        Log("INFO", "Registration success for device: " + device_id);
        return {true, "Registration successful", auth_code_vec, 0x00};
    }
    catch (const std::exception &e)
    {
        Log("ERROR", "Exception in RegisterDevice for device " + device_id + ": " + std::string(e.what()));
        return {false, "Registration failed due to exception", {}, 0xFF};
    }
}

LoginResult DeviceServiceImpl::LoginDevice(const UniversalParsedMessage &parsed_msg)
{
    const std::string raw_device_id = parsed_msg.GetField<std::string>("devUniqueId");
    const std::string device_id = NormalizeDeviceId(raw_device_id);
    const std::vector<uint8_t> auth_code_from_device = parsed_msg.GetField<std::vector<uint8_t>>("authentication_code");

    Log("INFO", "Processing login request from device: " + device_id);

    if (raw_device_id != device_id)
    {
        Log("DEBUG", "Normalized device_id from ['" + raw_device_id + "'] to ['" + device_id + "'] for login");
    }

    // 前置检查
    if (device_id.empty() || auth_code_from_device.empty())
    {
        Log("WARN", "Protocol error: missing device_id or authentication_code for login.");
        return {false, "Protocol error", 0x02, 0};
    }
    if ((!db_client_ || !db_client_->IsConnected()) || !cache_client_)
    {
        Log("ERROR", "Database or Cache client not available during login for device: " + device_id);
        return {false, "System error", 0x01, 0};
    }

    using namespace DPower::DB;
    std::optional<DPowerDeviceRecord> record_opt;

    // 鉴权码验证 (优先缓存)
    record_opt = cache_client_->GetDevice(device_id);
    if (!record_opt || (record_opt && record_opt->auth_code.empty()))
    {
        if (record_opt && record_opt->auth_code.empty())
        {
            Log("DEBUG", "Cache hit but auth_code empty for device: " + device_id + ", falling back to DB...");
        }
        else
        {
            Log("DEBUG", "Cache miss for device record during login: " + device_id + ". Querying database...");
        }
        DPowerDeviceRecord db_record;
        auto db_res = db_client_->GetDeviceById(device_id, db_record);
        if (!db_res.success)
        {
            Log("ERROR", "Database query failed for device " + device_id + ": " + db_res.error_message);
            return {false, "Database error", 0x01, 0};
        }
        if (!db_record.device_id.empty())
        {
            record_opt = db_record;
            cache_client_->SetDevice(db_record, 3600);
        }
    }

    if (!record_opt)
    {
        Log("WARN", "Login failed: Device " + device_id + " not found in system.");
        return {false, "Device not found", 0x02, 0};
    }

    const DPowerDeviceRecord &record = *record_opt;

    if (record.auth_code.empty())
    {
        Log("WARN", "Login failed: Device " + device_id + " is not registered yet.");
        return {false, "Device not registered", 0x01, 0};
    }

    // 统一归一化函数：将可能的HEX字符串或原始字节串转为稳定的16字节
    auto hex_nibble = [](char c) -> int
    {
        if (c >= '0' && c <= '9')
            return c - '0';
        if (c >= 'a' && c <= 'f')
            return 10 + (c - 'a');
        if (c >= 'A' && c <= 'F')
            return 10 + (c - 'A');
        return -1;
    };
    auto to16 = [&](const std::string &s) -> std::vector<uint8_t>
    {
        std::vector<uint8_t> out;
        if (s.empty())
            return out;
        bool is_hex = (s.size() % 2 == 0) && !s.empty();
        if (is_hex)
        {
            out.reserve(s.size() / 2);
            for (size_t i = 0; i < s.size(); i += 2)
            {
                int hi = hex_nibble(s[i]);
                int lo = hex_nibble(s[i + 1]);
                if (hi < 0 || lo < 0)
                {
                    is_hex = false;
                    break;
                }
                out.push_back(static_cast<uint8_t>((hi << 4) | lo));
                if (out.size() >= 16)
                    break; // 超过16字节即截断
            }
        }
        if (!is_hex)
        {
            out.assign(s.begin(), s.end());
        }
        if (out.size() > 16)
            out.resize(16);
        while (out.size() < 16)
            out.push_back(0);
        return out;
    };

    auto bytes_to_hex = [](const std::vector<uint8_t> &v)
    {
        std::ostringstream oss;
        oss << std::hex << std::setfill('0');
        for (auto b : v)
            oss << std::setw(2) << static_cast<int>(b);
        return oss.str();
    };

    std::vector<uint8_t> stored_vec = to16(record.auth_code);
    std::vector<uint8_t> device_vec = auth_code_from_device;
    if (device_vec.size() > 16)
        device_vec.resize(16);
    while (device_vec.size() < 16)
        device_vec.push_back(0);

    // 调试观察标准化后的HEX
    Log("DEBUG", "Auth code comparison (normalized) - Stored: " + bytes_to_hex(stored_vec) + ", Device: " + bytes_to_hex(device_vec));

    if (stored_vec == device_vec)
    {
        // 登录成功后的逻辑
        Log("INFO", "Login success for device: " + device_id);

        // 更新设备在线状态、最后在线时间和IP地址
        UpdateDeviceStatus(device_id, "online", parsed_msg.source_ip);

        // 注意：不在登录时记录心跳时间，等待第一个心跳消息
        // 这样可以避免设备登录后立即被离线检测线程误判为离线

        return {true, "Login successful", 0x00, 0};
    }
    else
    {
        // 登录失败的逻辑
        Log("WARN", "Login failed: Invalid authentication code for device: " + device_id);
        cache_client_->InvalidateDevice(device_id);
        return {false, "Invalid authentication code", 0x02, 0};
    }
}

std::vector<uint8_t> DeviceServiceImpl::ProcessHeartbeat(const UniversalParsedMessage &parsed_msg)
{
    const std::string raw_device_id = parsed_msg.GetField<std::string>("devUniqueId");
    const std::string device_id = NormalizeDeviceId(raw_device_id);
    Log("DEBUG", "Processing heartbeat from device: " + device_id);
    if (raw_device_id != device_id)
    {
        Log("DEBUG", "Normalized device_id from ['" + raw_device_id + "'] to ['" + device_id + "'] for heartbeat");
    }

    // 记录设备心跳时间
    {
        std::lock_guard<std::mutex> lock(device_status_mutex_);
        device_last_heartbeat_[device_id] = std::chrono::system_clock::now();
    }

    // 更新设备在线状态和最后在线时间
    UpdateDeviceStatus(device_id, "online", parsed_msg.source_ip);

    // 获取升级任务
    auto task_opt = GetUpgradeTask(device_id);

    if (task_opt.has_value())
    {
        std::string lock_key = "lock:upgrade_push:" + device_id;

        if (!cache_client_->KeyExists(lock_key))
        {
            Log("INFO", "[升级准备] 发现新任务，准备推送。将先返回 keep_connect=1 的心跳应答。");

            // 设置推送锁（存储在缓存Redis中）
            cache_client_->SetKey(lock_key, task_opt->task_id, 3600);

            // 安排异步推送
            auto task = *task_opt;
            auto shared_request_msg = std::make_shared<UniversalParsedMessage>(parsed_msg);
            auto response_gen = response_generator_;
            auto ftp_cfg = ftp_config_;
            auto mq_client = mq_client_;
            auto redis_queue_key = "device_responses"; // 使用配置中的响应队列键

            std::thread([response_gen, ftp_cfg, device_id, shared_request_msg, task, mq_client, redis_queue_key]()
                        {
                std::this_thread::sleep_for(std::chrono::milliseconds(500)); 
    
                try {
                    // 创建升级推送消息
                    uint16_t seq_num = shared_request_msg->GetField<uint16_t>("seNum");
                    std::vector<uint8_t> push_packet = response_gen->CreateUpgradePushMessage(device_id, seq_num, task, ftp_cfg, "dp_protocol_v1");
                    
                    // 创建响应对象并发送到Redis队列
                    DPower::Redis::DPowerRedisResponse response;
                    response.client_id = shared_request_msg->source_ip;
                    response.response_data_base64 = response_gen->Base64Encode(push_packet);
                    response.timestamp = std::chrono::system_clock::now();
                    
                    auto push_result = mq_client->PushResponse(redis_queue_key, response);
                    if (push_result.success) {
                        Utils::Logger::Instance().Log("INFO", std::string("[升级推送] 异步升级指令已发送: ") + device_id, "DeviceService");
                    } else {
                        Utils::Logger::Instance().Log("ERROR", std::string("[升级推送] 发送失败: ") + device_id, "DeviceService");
                    }
                } catch (const std::exception& e) {
                    Utils::Logger::Instance().Log("ERROR", std::string("[升级推送] 异常: ") + e.what(), "DeviceService");
                } })
                .detach();

            return response_generator_->CreateHeartbeatResponse(parsed_msg, 1);
        }
        else
        {
            Log("DEBUG", "Upgrade task found for " + device_id + ", but a push is already locked/in progress. Sending normal heartbeat.");
        }
    }
    else
    {
        Log("DEBUG", "No upgrade task found for " + device_id + ". Sending normal heartbeat response.");
    }

    return response_generator_->CreateHeartbeatResponse(parsed_msg, 0);
}

void DeviceServiceImpl::UpdateDeviceStatus(const std::string &device_id, const std::string &status, const std::string &source_ip)
{
    if (!db_client_ || !db_client_->IsConnected())
    {
        Log("ERROR", "Database client not available. Cannot update device status for " + device_id);
        return;
    }

    // 判断是否需要更新ip_endpoint，并确保IP不超过数据库字段长度限制
    bool update_ip_endpoint = (status == "online" && !source_ip.empty());
    std::string safe_ip = source_ip;
    if (safe_ip.length() > 45)
    { // IPv6最大长度39 + 端口号6 = 45
        safe_ip = safe_ip.substr(0, 45);
        Log("WARN", "IP endpoint truncated for device " + device_id + ": " + source_ip + " -> " + safe_ip);
    }

    auto status_update_res = db_client_->UpdateDeviceStatus(device_id, status, safe_ip, update_ip_endpoint);
    if (!status_update_res.success)
    {
        Log("ERROR", "Failed to update device status for " + device_id + ": " + status_update_res.error_message);
    }
    else
    {
        Log("INFO", "Device status updated successfully: " + device_id + " -> " + status + (update_ip_endpoint ? " (with IP update)" : " (IP preserved)"));
        // 使缓存失效，确保下次查询获取最新状态
        cache_client_->InvalidateDevice(device_id);
    }
}

std::optional<DPower::DB::DPowerUpgradeTask> DeviceServiceImpl::GetUpgradeTask(const std::string &device_id)
{
    // 1. 查缓存
    auto cached_task_result = cache_client_->GetUpgradeTask(device_id);
    if (!cached_task_result.has_value())
    {
        Log("DEBUG", "缓存未命中！");
    }
    else if (!cached_task_result.value().has_value())
    {
        Log("DEBUG", "缓存命中，确定没有任务！");
    }
    else
    {
        Log("DEBUG", "缓存命中，有任务！");
    }

    if (cached_task_result.has_value())
    {
        return *cached_task_result;
    }

    // 2. 缓存未命中，查数据库
    auto db_res = db_client_->GetPendingUpgradeTask(device_id);
    if (!db_res.first.success)
    {
        Log("ERROR", "Database query failed for upgrade task: " + db_res.first.error_message);
        return std::nullopt;
    }

    if (db_res.second.has_value())
    {
        auto &db_task = db_res.second.value();
        cache_client_->SetUpgradeTask(device_id, db_task, 60);
        return db_task;
    }
    else
    {
        cache_client_->SetUpgradeTask(device_id, std::nullopt, 30);
        return std::nullopt;
    }
}

void DeviceServiceImpl::StartOfflineDetection()
{
    if (offline_detection_running_.load())
    {
        return;
    }

    offline_detection_running_.store(true);
    offline_detection_thread_ = std::thread([this]()
                                            { OfflineDetectionThread(); });
}

void DeviceServiceImpl::StopOfflineDetection()
{
    if (!offline_detection_running_.load())
    {
        return;
    }

    offline_detection_running_.store(false);
    if (offline_detection_thread_.joinable())
    {
        offline_detection_thread_.join();
    }
}

void DeviceServiceImpl::OfflineDetectionThread()
{
    Log("INFO", "Offline detection thread started with timeout: " + std::to_string(heartbeat_timeout_.count()) + " seconds");

    while (offline_detection_running_.load())
    {
        auto now = std::chrono::system_clock::now();
        std::vector<std::string> offline_devices;

        {
            std::lock_guard<std::mutex> lock(device_status_mutex_);

            for (auto it = device_last_heartbeat_.begin(); it != device_last_heartbeat_.end(); ++it)
            {
                auto time_since_heartbeat = now - it->second;

                if (time_since_heartbeat > heartbeat_timeout_)
                {
                    offline_devices.push_back(it->first);
                }
            }
        }

        // 处理离线设备：在实际更新前后均进行二次校验，避免与新心跳竞争导致误判
        for (const auto &device_id : offline_devices)
        {
            bool still_offline = false;
            {
                std::lock_guard<std::mutex> lock(device_status_mutex_);
                auto it = device_last_heartbeat_.find(device_id);
                if (it != device_last_heartbeat_.end())
                {
                    if (now - it->second > heartbeat_timeout_)
                    {
                        still_offline = true;
                    }
                }
                else
                {
                    // 若不在表中，说明此前已被处理或从未记录，不再下线
                    still_offline = false;
                }
            }

            if (!still_offline)
            {
                continue; // 心跳已更新或无记录，跳过
            }

            // 在写库前再以当前时间戳进行一次快速校验，缩小竞态窗口
            auto now2 = std::chrono::system_clock::now();
            {
                std::lock_guard<std::mutex> lock(device_status_mutex_);
                auto it = device_last_heartbeat_.find(device_id);
                if (it != device_last_heartbeat_.end())
                {
                    if (!(now2 - it->second > heartbeat_timeout_))
                    {
                        continue; // 刚刚收到新心跳，放弃离线更新
                    }
                }
                else
                {
                    continue;
                }
            }

            // 标记离线（DB 更新）
            UpdateDeviceStatus(device_id, "offline", "");

            // 再次确认仍旧超时后再移除记录，防止在DB更新期间有新心跳到达
            {
                std::lock_guard<std::mutex> lock(device_status_mutex_);
                auto it = device_last_heartbeat_.find(device_id);
                if (it != device_last_heartbeat_.end())
                {
                    if (now2 - it->second > heartbeat_timeout_)
                    {
                        device_last_heartbeat_.erase(it);
                    }
                }
            }
        }

        // 每5秒检查一次
        std::this_thread::sleep_for(std::chrono::seconds(5));
    }

    Log("INFO", "Offline detection thread stopped");
}

bool DeviceServiceImpl::IsAllPaddingChars(const std::string &str)
{
    if (str.empty())
    {
        return true;
    }

    // 检查是否所有字符都是填充字符
    for (size_t i = 0; i < str.length(); ++i)
    {
        char c = str[i];
        uint8_t byte = static_cast<uint8_t>(c);
        // 检查是否为常见的填充字符：0x00, 0xFF, 0x20 (空格)
        if (byte != 0x00 && byte != 0xFF && byte != 0x20)
        {
            return false;
        }
    }

    return true;
}

void DeviceServiceImpl::Log(const std::string &level, const std::string &message) const
{
    Utils::Logger::Instance().Log(level, message, "DeviceService");
}
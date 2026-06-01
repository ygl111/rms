#include "logic/services/FaultServiceImpl.h"
#include "logic/utils/MessageUtils.h"
#include "logic/utils/Logger.h"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <ctime>

// 规范化设备ID：去除尾部 0x00/0xFF/空白与首部空白，不改变大小写
static std::string NormalizeDeviceId(std::string s) {
    while (!s.empty()) {
        unsigned char b = static_cast<unsigned char>(s.back());
        if (b == 0x00 || b == 0xFF || b == 0x20 || b == '\r' || b == '\n' || b == '\t') {
            s.pop_back();
        } else {
            break;
        }
    }
    size_t start = 0;
    while (start < s.size()) {
        unsigned char b = static_cast<unsigned char>(s[start]);
        if (b == 0x20 || b == '\r' || b == '\n' || b == '\t') {
            ++start;
        } else {
            break;
        }
    }
    if (start > 0) s.erase(0, start);
    return s;
}

static std::time_t TimegmUtc(std::tm* tm) {
#if defined(_WIN32)
    return _mkgmtime(tm);
#else
    return timegm(tm);
#endif
}

FaultServiceImpl::FaultServiceImpl(
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
    DPower::Notify::EmailNotifierPtr email_notifier)
    : db_client_(std::move(db_client)),
      cache_client_(std::move(cache_client)),
      mq_client_(std::move(mq_client)),
      email_notifier_(std::move(email_notifier))
{
}

FaultReportResult FaultServiceImpl::ProcessFaultReport(const UniversalParsedMessage& parsed_msg) {
    try {
        // 获取设备ID
        std::string raw_device_id = parsed_msg.GetField<std::string>("devUniqueId");
        std::string device_id = NormalizeDeviceId(raw_device_id);
        if (device_id.empty()) {
            Log("ERROR", "Missing device ID in fault report");
            return {false, "Missing device ID", 0x03}; // 报文不正确
        }
        if (raw_device_id != device_id) {
            Log("DEBUG", "Normalized device_id from ['" + raw_device_id + "'] to ['" + device_id + "'] in fault report");
        }
        Log("INFO", "Processing fault report from device: " + device_id);
        
        // 日志与调试代码
        Log("DEBUG", "ParsedMessage JSON: " + MessageUtils::MessageToJson(parsed_msg));
        
        // 检查数据库连接
        if (!db_client_) {
            Log("ERROR", "Database client not available for device: " + device_id);
            return {false, "Database not available", 0x01}; // 失败
        }
        
        // 构建故障记录
        DPower::DB::DPowerFaultRecord fault_record;
        fault_record.id = ""; // 数据库自动生成UUID
        fault_record.device_id = device_id;
        fault_record.status = "unprocessed";
        
        // 解析故障数据
        if (parsed_msg.HasField("event_level")) {
            fault_record.fault_level = static_cast<int>(parsed_msg.GetField<uint8_t>("event_level"));
        }
        
        if (parsed_msg.HasField("event_code")) {
            uint16_t event_code = parsed_msg.GetField<uint16_t>("event_code");
            fault_record.fault_code = std::to_string(event_code);
            Log("DEBUG", "Extracted event_code: " + fault_record.fault_code);
        } else {
            Log("DEBUG", "event_code field not found in parsed message");
        }
        
        if (parsed_msg.HasField("event_time")) {
            std::string event_time_str = parsed_msg.GetField<std::string>("event_time");
            fault_record.fault_time = ParseBcdTimeString(event_time_str);
        } else {
            fault_record.fault_time = std::chrono::system_clock::now();
        }
        
        if (parsed_msg.HasField("event_content")) {
            // 将解析出的事件内容写入描述
            fault_record.description = parsed_msg.GetField<std::string>("event_content");
            Log("DEBUG", "Extracted event_content: '" + fault_record.description + "'");
        } else {
            Log("DEBUG", "event_content field not found in parsed message");
        }
        
        // 不操作 extra_data（预留字段）
        
        // 保存到数据库
        auto db_result = db_client_->InsertFaultRecord(fault_record);
        if (!db_result.success) {
            Log("ERROR", "Failed to save fault report to database for device " + device_id + ": " + db_result.error_message);
            return {false, db_result.error_message, 0x01}; // 失败
        }
        
        Log("INFO", "Successfully saved fault report for device: " + device_id);
        
        // 异步发送故障邮件通知
        if (email_notifier_) {
            std::string level_str;
            if (parsed_msg.HasField("event_level")) {
                level_str = std::to_string(static_cast<int>(parsed_msg.GetField<uint8_t>("event_level")));
            }
            email_notifier_->EnqueueFaultEmail(device_id, fault_record.fault_code, fault_record.description, level_str);
        }
        
        return {true, "", 0x00}; // 成功
        
    } catch (const std::exception& e) {
        Log("ERROR", "Exception in ProcessFaultReport: " + std::string(e.what()));
        return {false, e.what(), 0x01}; // 失败
    }
}

std::chrono::system_clock::time_point FaultServiceImpl::ParseBcdTimeString(const std::string& bcd_time_str) {
    if (bcd_time_str.length() != 12) { // YYMMDDHHMMSS = 12 characters
        Log("WARN", "Invalid BCD time format, using current time");
        return std::chrono::system_clock::now();
    }
    
    try {
        // 解析字符串格式的BCD时间：YYMMDDHHMMSS
        int year = 2000 + std::stoi(bcd_time_str.substr(0, 2));
        int month = std::stoi(bcd_time_str.substr(2, 2));
        int day = std::stoi(bcd_time_str.substr(4, 2));
        int hour = std::stoi(bcd_time_str.substr(6, 2));
        int minute = std::stoi(bcd_time_str.substr(8, 2));
        int second = std::stoi(bcd_time_str.substr(10, 2));
        
        // 构建时间点
        std::tm tm = {};
        tm.tm_year = year - 1900;
        tm.tm_mon = month - 1;
        tm.tm_mday = day;
        tm.tm_hour = hour;
        tm.tm_min = minute;
        tm.tm_sec = second;
        
        tm.tm_isdst = 0;
        const std::time_t time_seconds = TimegmUtc(&tm);
        if (time_seconds == static_cast<std::time_t>(-1)) {
            Log("WARN", "Failed to convert BCD time via TimegmUtc, using current time");
            return std::chrono::system_clock::now();
        }
        return std::chrono::system_clock::from_time_t(time_seconds);
        
    } catch (const std::exception& e) {
        Log("WARN", "Failed to parse BCD time string: " + std::string(e.what()) + ", using current time");
        return std::chrono::system_clock::now();
    }
}

std::chrono::system_clock::time_point FaultServiceImpl::ParseBcdTime(const std::vector<uint8_t>& bcd_time) {
    if (bcd_time.size() != 6) {
        Log("WARN", "Invalid BCD time format, using current time");
        return std::chrono::system_clock::now();
    }
    
    try {
        // BCD格式：YY MM DD HH MM SS
        int year = 2000 + ((bcd_time[0] >> 4) * 10 + (bcd_time[0] & 0x0F));
        int month = ((bcd_time[1] >> 4) * 10 + (bcd_time[1] & 0x0F));
        int day = ((bcd_time[2] >> 4) * 10 + (bcd_time[2] & 0x0F));
        int hour = ((bcd_time[3] >> 4) * 10 + (bcd_time[3] & 0x0F));
        int minute = ((bcd_time[4] >> 4) * 10 + (bcd_time[4] & 0x0F));
        int second = ((bcd_time[5] >> 4) * 10 + (bcd_time[5] & 0x0F));
        
        // 构建时间点
        std::tm tm = {};
        tm.tm_year = year - 1900;
        tm.tm_mon = month - 1;
        tm.tm_mday = day;
        tm.tm_hour = hour;
        tm.tm_min = minute;
        tm.tm_sec = second;
        
        tm.tm_isdst = 0;
        const std::time_t time_seconds = TimegmUtc(&tm);
        if (time_seconds == static_cast<std::time_t>(-1)) {
            Log("WARN", "Failed to convert raw BCD time via TimegmUtc, using current time");
            return std::chrono::system_clock::now();
        }
        return std::chrono::system_clock::from_time_t(time_seconds);
        
    } catch (const std::exception& e) {
        Log("WARN", "Failed to parse BCD time: " + std::string(e.what()) + ", using current time");
        return std::chrono::system_clock::now();
    }
}

void FaultServiceImpl::Log(const std::string& level, const std::string& message) const {
    Utils::Logger::Instance().Log(level, message, "FaultService");
}
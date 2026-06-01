#include "logic/services/BanknoteServiceImpl.h"
#include "logic/utils/MessageUtils.h"
#include "logic/utils/Logger.h"
#include <json.hpp>
#include <chrono>
#include <ctime>
#include <iostream>
#include <sstream>

// 规范化设备ID：去掉报文中的填充字节和首尾空格，避免 DB 精确匹配失败
static std::string NormalizeDeviceId(std::string s) {
    // 去掉尾部填充字节：0x00, 0xFF, 空格、控制字符
    while (!s.empty()) {
        unsigned char b = static_cast<unsigned char>(s.back());
        if (b == 0x00 || b == 0xFF || b == 0x20 || b == '\r' || b == '\n' || b == '\t') {
            s.pop_back();
        } else {
            break;
        }
    }
    // 去掉首部空白字符
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

static std::chrono::system_clock::time_point ParseCountingTimeUtc(const std::string& bcd_time_str) {
    if (bcd_time_str.length() != 12) {
        Utils::Logger::Instance().Log("WARN", "Invalid counting_time length, fallback to current time", "BanknoteService");
        return std::chrono::system_clock::now();
    }

    try {
        const int year = 2000 + std::stoi(bcd_time_str.substr(0, 2));
        const int month = std::stoi(bcd_time_str.substr(2, 2));
        const int day = std::stoi(bcd_time_str.substr(4, 2));
        const int hour = std::stoi(bcd_time_str.substr(6, 2));
        const int minute = std::stoi(bcd_time_str.substr(8, 2));
        const int second = std::stoi(bcd_time_str.substr(10, 2));

        std::tm tm = {};
        tm.tm_year = year - 1900;
        tm.tm_mon = month - 1;
        tm.tm_mday = day;
        tm.tm_hour = hour;
        tm.tm_min = minute;
        tm.tm_sec = second;
        tm.tm_isdst = 0; // 设备数据已为UTC，不做夏令时调整

        const std::time_t timestamp = TimegmUtc(&tm);
        if (timestamp == static_cast<std::time_t>(-1)) {
            Utils::Logger::Instance().Log("WARN", "Failed to convert counting_time via TimegmUtc, fallback to current time", "BanknoteService");
            return std::chrono::system_clock::now();
        }

        return std::chrono::system_clock::from_time_t(timestamp);
    } catch (const std::exception& e) {
        Utils::Logger::Instance().Log("WARN", std::string("Exception while parsing counting_time: ") + e.what(), "BanknoteService");
        return std::chrono::system_clock::now();
    }
}

BanknoteServiceImpl::BanknoteServiceImpl(
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
        std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client,
        std::shared_ptr<DPower::MQ::DPowerMqClient> rabbitmq_client,
        std::string worktime_queue_name)
    : db_client_(std::move(db_client)),
      cache_client_(std::move(cache_client)),
            mq_client_(std::move(mq_client)),
            rabbitmq_client_(std::move(rabbitmq_client)),
            worktime_queue_name_(std::move(worktime_queue_name))
{
}

BanknoteReportResult BanknoteServiceImpl::ProcessBanknoteReport(const UniversalParsedMessage& parsed_msg) {
    try {
        // 获取设备ID
        if (!parsed_msg.HasField("devUniqueId")) {
            Log("ERROR", "Missing device ID in banknote report");
            return {false, "Missing device ID", 0x03}; // 报文不正确
        }
        
        const std::string raw_device_id = parsed_msg.GetField<std::string>("devUniqueId");
        const std::string device_id = NormalizeDeviceId(raw_device_id);
        if (raw_device_id != device_id) {
            Log("DEBUG", "Normalized device_id from ['" + raw_device_id + "'] to ['" + device_id + "']");
        }
        Log("INFO", "Processing banknote report from device: " + device_id);
        
        // 日志解析结果
        Log("INFO", "ParsedMessage JSON: " + MessageUtils::MessageToJson(parsed_msg));
        
        // 检查数据库连接
        if (!db_client_) {
            Log("ERROR", "Database client not available for device: " + device_id);
            return {false, "Database not available", 0x01}; // 失败
        }
        
        // 解析基本字段
        uint8_t work_mode = parsed_msg.GetField<uint8_t>("work_mode");
        uint8_t business_mode = parsed_msg.GetField<uint8_t>("business_mode");
        uint8_t add_up_switch = parsed_msg.GetField<uint8_t>("add_up_switch");
        uint16_t total_notes_count = parsed_msg.GetField<uint16_t>("total_notes_count");
        uint8_t currency_count = parsed_msg.GetField<uint8_t>("currency_count");
        uint32_t duration_ms = 0;
        if (parsed_msg.HasField("duration_ms")) {
            duration_ms = parsed_msg.GetField<uint32_t>("duration_ms");
        } else {
            Log("INFO", "duration_ms missing, defaulting to 0");
        }
        
        // 解析计数时间（设备提供的UTC BCD时间）
        std::chrono::system_clock::time_point count_time_point = std::chrono::system_clock::now();
        if (parsed_msg.HasField("counting_time")) {
            const std::string counting_time_str = parsed_msg.GetField<std::string>("counting_time");
            count_time_point = ParseCountingTimeUtc(counting_time_str);
        } else {
            Log("WARN", "counting_time field missing in parsed message, fallback to current time");
        }
        
        // 计算统计数据
        uint64_t total_amount_cents = 0;     // 仅统计“通过”的金额（单位：分）
        uint16_t passed_count_details = 0;   // 仅统计“通过”的张数（来自明细）
        uint16_t failed_count = 0;           // 统计 error_code != 0 的张数
        
        // 声明statistics_data变量，使其在整个函数中可用
        std::vector<CountInfo> statistics_data;
        
        // 根据钞票明细数据重新计算按面额分组的统计数据
        bool details_consumed = false;
        if (parsed_msg.HasField("note_details")) {
            // 检查字段类型，避免类型转换错误
            auto it = parsed_msg.extracted_fields.find("note_details");
            if (it != parsed_msg.extracted_fields.end() && std::holds_alternative<std::vector<NoteInfo>>(it->second)) {
                auto note_details = std::get<std::vector<NoteInfo>>(it->second);
                details_consumed = true;

                // 临时结构: 包含面额字段用于按面额分组统计(仅统计通过的钞票)
                struct DenominationStat {
                    std::string currency_symbol;
                    uint32_t denomination;
                    uint16_t count;
                    uint64_t amount;
                };
                std::map<uint32_t, DenominationStat> denomination_stats;

                for (const auto& note : note_details) {
                    // 拒钞判断：钞口为0xFF（255）
                    // 通过判断：error_group == 0 且 error_type == 0
                    bool is_rejected = (note.stacker == 0xFF);
                    bool is_passed = (note.error_group == 0 && note.error_type == 0);
                    
                    if (is_rejected || !is_passed) {
                        ++failed_count;
                        continue; // 不计入"通过"统计
                    }

                    // 统计通过的钞票（error_group == 0 且 error_type == 0 且 stacker != 0xFF）
                    if (denomination_stats.find(note.denomination) == denomination_stats.end()) {
                        DenominationStat new_stat;
                        new_stat.currency_symbol = note.currency_symbol;
                        new_stat.denomination = note.denomination;
                        new_stat.count = 0;
                        new_stat.amount = 0;
                        denomination_stats[note.denomination] = new_stat;
                    }
                    denomination_stats[note.denomination].count++;
                    denomination_stats[note.denomination].amount += note.denomination;
                }

                // 转换为 CountInfo（协议格式，不包含 denomination 字段）并累加总通过张数/金额
                for (const auto& pair : denomination_stats) {
                    CountInfo stat;
                    stat.currency_symbol = pair.second.currency_symbol;
                    stat.count = pair.second.count;
                    stat.amount = pair.second.amount;
                    statistics_data.push_back(stat);
                    total_amount_cents += pair.second.amount;
                    passed_count_details += pair.second.count;
                }

                Log("INFO", "Generated " + std::to_string(statistics_data.size()) + " denomination-based statistics records from " +
                        std::to_string(note_details.size()) + " note details (passed=" + std::to_string(passed_count_details) + ", failed=" + std::to_string(failed_count) + ")");
            } else {
                Log("WARNING", "note_details field exists but is not a valid NoteInfo vector");
            }
        } else {
            Log("WARNING", "No note_details field found in parsed message");
        }
        
        // 若未能从明细生成统计，则尝试直接使用解析结果中的统计数据
        if (statistics_data.empty() && parsed_msg.HasField("statistics_data")) {
            auto stats_it = parsed_msg.extracted_fields.find("statistics_data");
            if (stats_it != parsed_msg.extracted_fields.end() &&
                std::holds_alternative<std::vector<CountInfo>>(stats_it->second)) {
                const auto& parsed_stats = std::get<std::vector<CountInfo>>(stats_it->second);
                statistics_data.insert(statistics_data.end(), parsed_stats.begin(), parsed_stats.end());
                for (const auto& stat : parsed_stats) {
                    total_amount_cents += stat.amount;
                    passed_count_details += stat.count;
                }
                Log("INFO", "Using parser-provided statistics_data records=" + std::to_string(statistics_data.size()));
            }
        }

        // 若没有成功解析明细，无法获知失败张数，回退为 0（保持安全口径）
        if (!details_consumed) {
            failed_count = 0;
        }
        
        // 构建点钞记录
        DPower::DB::BanknoteCountReport banknote_report;
        banknote_report.id = ""; // 数据库自动生成UUID
        banknote_report.device_id = device_id;
        banknote_report.work_mode = work_mode;
        banknote_report.business_mode = business_mode;
        banknote_report.accumulate_flag = add_up_switch;
        banknote_report.count_time = count_time_point;
        // 注意：这里 total_passed_count 字段存储“总张数”（来自报文 total_notes_count），非仅通过张数
        banknote_report.total_passed_count = total_notes_count;
        banknote_report.failed_count = failed_count;
        banknote_report.total_amount = static_cast<double>(total_amount_cents) / 100.0;
        banknote_report.currency_count = currency_count;
        banknote_report.device_identifier = device_id;
        
        // 填充按面额分组的统计数据
        for (const auto& stat : statistics_data) {
            // 数据验证：检查数据的合理性
            if (stat.count > 0 || stat.amount > 0) {
                DPower::DB::BanknoteCurrencyStat currency_stat;
                currency_stat.count_id = banknote_report.id;
                currency_stat.currency_code = stat.currency_symbol;
                
                // 注意: statistics_data 中没有面额字段，只有总金额和张数
                // 计算平均面额: value = amount / count (处理拒钞或错钞情况：amount可能为0)
                if (stat.count > 0 && stat.amount > 0) {
                    currency_stat.value = static_cast<double>(stat.amount) / static_cast<double>(stat.count) / 100.0;
                } else {
                    currency_stat.value = 0.0;  // 拒钞或错钞，面额为0
                }
                
                currency_stat.note_count = stat.count;
                currency_stat.amount = static_cast<double>(stat.amount) / 100.0;
                
                banknote_report.currency_stats.push_back(currency_stat);
            }
        }
        
        // 填充钞票明细数据
        if (parsed_msg.HasField("note_details")) {
            // 检查字段类型，避免类型转换错误
            auto it = parsed_msg.extracted_fields.find("note_details");
            if (it != parsed_msg.extracted_fields.end() && std::holds_alternative<std::vector<NoteInfo>>(it->second)) {
                auto note_details = std::get<std::vector<NoteInfo>>(it->second);
                uint32_t detail_seq = 1;
                for (const auto& note : note_details) {
                    // 保存所有钞票（包括面值为0的拒钞），面值为0时 note_value 存 0
                    DPower::DB::BanknoteDetailRecord detail_record;
                    detail_record.count_id = banknote_report.id;
                    detail_record.seq = detail_seq++;
                    detail_record.currency_code = note.currency_symbol;
                    detail_record.note_value = static_cast<double>(note.denomination) / 100.0; // TODO: 若协议面额已是元，应去掉 /100
                    detail_record.note_version = note.note_version;
                    detail_record.error_group = note.error_group;
                    detail_record.error_type = note.error_type;
                    detail_record.error_code = note.error_code;
                    detail_record.serial_number = note.serial_number;
                    detail_record.stacker = note.stacker;
                    banknote_report.details.push_back(detail_record);
                }
            }
        }
        
        // 保存完整记录到数据库（包括币种统计和钞票明细）
        auto db_result = db_client_->SaveBanknoteReport(banknote_report);
        if (!db_result.success) {
            Log("ERROR", "Failed to save banknote report to database for device " + device_id + ": " + db_result.error_message);
            return {false, db_result.error_message, 0x01}; // 失败
        }

        // Persist work time detail for counting session
        DPower::DB::DeviceWorkTimeDetail work_time_detail{device_id, count_time_point, duration_ms};
        auto work_time_result = db_client_->InsertDeviceWorkTimeDetail(work_time_detail);
        if (!work_time_result.success) {
            Log("ERROR", "Failed to insert device_work_time_detail for device " + device_id + ": " + work_time_result.error_message);
            return {false, work_time_result.error_message, 0x01};
        }

        // 工作时长写库成功后，将 detail_id 推送到 RabbitMQ 供 Python 后端聚合。
        if (work_time_detail.detail_id.empty()) {
            Log("WARN", "device_work_time_detail inserted but detail_id is empty, skip RabbitMQ publish");
        } else if (!rabbitmq_client_) {
            Log("WARN", "RabbitMQ client is not configured, skip worktime detail publish");
        } else if (!rabbitmq_client_->IsConnected()) {
            Log("WARN", "RabbitMQ client is not connected, skip worktime detail publish, detail_id=" + work_time_detail.detail_id);
        } else {
            nlohmann::json payload;
            payload["detail_id"] = work_time_detail.detail_id;
            const std::string queue_name = worktime_queue_name_.empty() ? "worktime_detail_queue" : worktime_queue_name_;
            auto mq_publish_result = rabbitmq_client_->Publish(queue_name, payload.dump(), true);
            if (!mq_publish_result.success) {
                Log("ERROR", "Failed to publish worktime detail to RabbitMQ, detail_id=" + work_time_detail.detail_id + ", error=" + mq_publish_result.error_message);
            }
        }
        
        Log("INFO", "Successfully saved banknote report for device: " + device_id + 
            " (Total: " + std::to_string(total_notes_count) + 
            ", Passed: " + std::to_string(passed_count_details) + 
            ", Failed: " + std::to_string(failed_count) + 
            ", Amount: " + std::to_string(static_cast<double>(total_amount_cents) / 100.0) + 
            ", Currency records: " + std::to_string(banknote_report.currency_stats.size()) + 
            ", Detail records: " + std::to_string(banknote_report.details.size()) + ")");
        
        return {true, "", 0x00}; // 成功
        
    } catch (const std::exception& e) {
        Log("ERROR", "Exception in ProcessBanknoteReport: " + std::string(e.what()));
        return {false, e.what(), 0x01}; // 失败
    }
}

void BanknoteServiceImpl::Log(const std::string& level, const std::string& message) const {
    Utils::Logger::Instance().Log(level, message, "BanknoteService");
}

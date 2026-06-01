#include "logic/services/BanknoteServiceImpl.h"
#include "logic/utils/MessageUtils.h"
#include "logic/utils/Logger.h"
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

BanknoteServiceImpl::BanknoteServiceImpl(
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client)
    : db_client_(std::move(db_client)),
      cache_client_(std::move(cache_client)),
      mq_client_(std::move(mq_client))
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
        
        // 解析计数时间（BCD格式）
        std::string counting_time_str = parsed_msg.GetField<std::string>("counting_time");
        
        // 计算统计数据
        uint32_t total_amount = 0;           // 仅统计“通过”的金额
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

                // 按面额分组统计（仅统计通过的钞票，error_code == 0）
                std::map<uint32_t, CountInfo> denomination_stats;

                for (const auto& note : note_details) {
                    // 失败条件：1) error_code 非 0  2) 面值为 0（拒钞/未识别）
                    if (note.error_code != 0 || note.denomination == 0) {
                        ++failed_count;
                        continue; // 不计入“通过”统计
                    }

                    // 统计通过：面值>0 且 error_code==0
                    if (denomination_stats.find(note.denomination) == denomination_stats.end()) {
                        CountInfo new_stat;
                        new_stat.currency_symbol = note.currency_symbol;
                        new_stat.denomination = note.denomination;
                        new_stat.count = 0;
                        new_stat.amount = 0;
                        denomination_stats[note.denomination] = new_stat;
                    }
                    denomination_stats[note.denomination].count++;
                    denomination_stats[note.denomination].amount += note.denomination;
                }

                // 将按面额分组的统计数据转换为 vector，并累加总通过张数/金额
                for (const auto& pair : denomination_stats) {
                    statistics_data.push_back(pair.second);
                    total_amount += pair.second.amount;
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
        banknote_report.count_time = std::chrono::system_clock::now();
        // 注意：这里 total_passed_count 字段存储“总张数”（来自报文 total_notes_count），非仅通过张数
        banknote_report.total_passed_count = total_notes_count;
        banknote_report.failed_count = failed_count;
        banknote_report.total_amount = total_amount / 100; // 转换为元（分转元）
        banknote_report.currency_count = currency_count;
        
        // 填充按面额分组的统计数据
        for (const auto& stat : statistics_data) {
            // 数据验证：检查数据的合理性
            if (stat.count > 0 || stat.amount > 0) {
                DPower::DB::BanknoteCurrencyStat currency_stat;
                currency_stat.count_id = banknote_report.id;
                currency_stat.currency_code = stat.currency_symbol;
                
                // 数据验证：确保面值不为0（如果张数或金额不为0）
                if (stat.denomination == 0 && (stat.count > 0 || stat.amount > 0)) {
                    Log("WARNING", "Invalid denomination: 0 for currency " + stat.currency_symbol + 
                        " with count=" + std::to_string(stat.count) + ", amount=" + std::to_string(stat.amount));
                    // 跳过无效记录
                    continue;
                }
                
                currency_stat.value = stat.denomination / 100; // 转换为元（分转元）
                currency_stat.note_count = stat.count;
                currency_stat.amount = stat.amount / 100; // 转换为元（分转元）
                
                banknote_report.currency_stats.push_back(currency_stat);
            }
        }
        
        // 填充钞票明细数据
        if (parsed_msg.HasField("note_details")) {
            // 检查字段类型，避免类型转换错误
            auto it = parsed_msg.extracted_fields.find("note_details");
            if (it != parsed_msg.extracted_fields.end() && std::holds_alternative<std::vector<NoteInfo>>(it->second)) {
                auto note_details = std::get<std::vector<NoteInfo>>(it->second);
                for (const auto& note : note_details) {
                    // 保存所有钞票（包括面值为0的拒钞），面值为0时 note_value 存 0
                    DPower::DB::BanknoteDetailRecord detail_record;
                    detail_record.count_id = banknote_report.id;
                    detail_record.currency_code = note.currency_symbol;
                    detail_record.note_value = note.denomination / 100; // TODO: 若协议面额已是元，应去掉 /100
                    detail_record.note_version = note.note_version;
                    detail_record.error_type = note.error_type;
                    detail_record.error_code = note.error_code;
                    detail_record.serial_number = note.serial_number;
                    detail_record.stacker = 0; // 默认值（后续如需区分出钞位置可扩展）
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
        
        Log("INFO", "Successfully saved banknote report for device: " + device_id + 
            " (Total: " + std::to_string(total_notes_count) + 
            ", Passed: " + std::to_string(passed_count_details) + 
            ", Failed: " + std::to_string(failed_count) + 
            ", Amount: " + std::to_string(total_amount) + 
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

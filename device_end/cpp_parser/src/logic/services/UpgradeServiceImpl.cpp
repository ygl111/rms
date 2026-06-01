#include "logic/services/UpgradeServiceImpl.h"
#include "logic/utils/MessageUtils.h"
#include "logic/utils/Logger.h"
#include <iostream>
#include <sstream>
#include <cctype>
#include <algorithm>

// 规范化设备ID：去掉报文中的填充字节和首尾空白（不改变大小写）
static std::string NormalizeDeviceId(std::string s) {
    // 去掉尾部填充字节：0x00, 0xFF, 空格以及常见空白\r\n\t
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

UpgradeServiceImpl::UpgradeServiceImpl(
    std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
    std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client,
    std::shared_ptr<DPower::Redis::DPowerRedisClient> mq_client)
    : db_client_(std::move(db_client)),
      cache_client_(std::move(cache_client)),
      mq_client_(std::move(mq_client))
{
}

UpgradeResultReportResult UpgradeServiceImpl::ProcessUpgradeResultReport(const UniversalParsedMessage& parsed_msg) {
    try {
        // 获取设备ID
        std::string raw_device_id = parsed_msg.GetField<std::string>("devUniqueId");
        std::string device_id = NormalizeDeviceId(raw_device_id);
        if (device_id.empty()) {
            Log("ERROR", "Missing device ID in upgrade result report");
            return {false, "Missing device ID", 0x03}; // 报文不正确
        }
        if (raw_device_id != device_id) {
            Log("DEBUG", "Normalized device_id from ['" + raw_device_id + "'] to ['" + device_id + "'] in upgrade result");
        }
        Log("INFO", "Processing upgrade result report from device: " + device_id);
        
        // 日志与调试代码
        Log("DEBUG", "ParsedMessage JSON: " + MessageUtils::MessageToJson(parsed_msg));
        
        // 检查数据库连接
        if (!db_client_) {
            Log("ERROR", "Database client not available for device: " + device_id);
            return {false, "Database not available", 0x01}; // 失败
        }
        
        // 解析升级结果数据
        std::string upgrade_result = "unknown";
        std::string firmware_version = "";
        std::string task_id = "";
        
        // 从消息体中解析upgrade_task_id
        if (parsed_msg.HasField("upgrade_task_id")) {
            task_id = parsed_msg.GetField<std::string>("upgrade_task_id");
            if (!task_id.empty()) {
                size_t first = task_id.find_first_not_of(" \t\r\n");
                if (first != std::string::npos && first > 0) {
                    task_id.erase(0, first);
                }
                size_t last = task_id.find_last_not_of(" \t\r\n");
                if (last != std::string::npos) {
                    task_id.erase(last + 1);
                }
            }
            // 截断到第一个 NUL，避免隐藏字符
            size_t nul_pos = task_id.find('\0');
            if (nul_pos != std::string::npos) {
                task_id.erase(nul_pos);
            }
        }

        uint8_t upgrade_channel = parsed_msg.GetField<uint8_t>("upgrade_channel", 0xFF);

        std::string task_id_compact;
        task_id_compact.reserve(task_id.size());
        for (char ch : task_id) {
            if (!std::isspace(static_cast<unsigned char>(ch))) {
                task_id_compact.push_back(ch);
            }
        }
        bool ascii_zero_task_id = !task_id_compact.empty() &&
                                  std::all_of(task_id_compact.begin(), task_id_compact.end(),
                                              [](char c) { return c == '0'; });
        bool missing_task_id = task_id_compact.empty();
        bool allow_placeholder_task = (upgrade_channel == 1 || upgrade_channel == 5);
        bool skip_task_flow = false;

        if ((missing_task_id || ascii_zero_task_id) && allow_placeholder_task) {
            skip_task_flow = true;
            Log("INFO", "Upgrade result report uses placeholder task id on channel " +
                std::to_string(upgrade_channel) + " for device: " + device_id);
        } else if (missing_task_id) {
            Log("ERROR", "Missing upgrade_task_id in upgrade result report for device: " + device_id);
            return {false, "Missing upgrade_task_id", 0x03}; // 报文不正确
        }

        // 解析升级结果
        if (parsed_msg.HasField("upgrade_result")) {
            uint8_t result_value = parsed_msg.GetField<uint8_t>("upgrade_result");
            switch (result_value) {
                case 0:
                    upgrade_result = "success";
                    break;
                case 1:
                    upgrade_result = "failed";
                    break;
                case 2:
                    upgrade_result = "in_progress";
                    break;
                default:
                    upgrade_result = "unknown";
                    break;
            }
        }
        
        // 解析当前版本号
        if (parsed_msg.HasField("current_version")) {
            firmware_version = parsed_msg.GetField<std::string>("current_version");
            if (!firmware_version.empty()) {
                size_t last = firmware_version.find_last_not_of(" \t\r\n");
                if (last == std::string::npos) {
                    firmware_version.clear();
                } else if (last + 1 < firmware_version.size()) {
                    firmware_version.erase(last + 1);
                }
            }

            // 如果包含NUL或全部为0xFF，则视为无效
            auto is_all_ff = [](const std::string& s) {
                if (s.empty()) return false; // 空串另行判断
                for (unsigned char c : s) {
                    if (c != 0xFF) return false;
                }
                return true;
            };
            if (firmware_version.empty() || firmware_version.find('\0') != std::string::npos || is_all_ff(firmware_version)) {
                firmware_version = "";
            }
        }
        
        // 根据upgrade_result确定状态
        DPower::DB::DPowerUpgradeStatus status = DPower::DB::DPowerUpgradeStatus::Failed;
        if (upgrade_result == "success") {
            status = DPower::DB::DPowerUpgradeStatus::Completed;
        } else if (upgrade_result == "in_progress") {
            status = DPower::DB::DPowerUpgradeStatus::InProgress;
        }
        
        // 解析失败描述（如果有）——兼容两种字段名
        std::string failure_desc = "";
        if (parsed_msg.HasField("failure_description")) {
            failure_desc = parsed_msg.GetField<std::string>("failure_description");
        } else if (parsed_msg.HasField("failure_desc")) {
            failure_desc = parsed_msg.GetField<std::string>("failure_desc");
        }
        if (!failure_desc.empty()) {
            size_t last = failure_desc.find_last_not_of(" \t\r\n");
            if (last == std::string::npos) {
                failure_desc.clear();
            } else if (last + 1 < failure_desc.size()) {
                failure_desc.erase(last + 1);
            }
            // 截断到第一个\0，避免写入不可见字符
            size_t nul_pos = failure_desc.find('\0');
            if (nul_pos != std::string::npos) {
                failure_desc.erase(nul_pos);
            }
            if (failure_desc.empty()) {
                failure_desc = "";
            }
        }
        
        // 构建结果消息，确保所有字符串都是安全的
        std::string result_message = "Upgrade result: " + upgrade_result;
        if (!firmware_version.empty()) {
            result_message += ", Version: " + firmware_version;
        }
        if (!failure_desc.empty()) {
            result_message += ", Failure: " + failure_desc;
        }
        
        // 确保结果消息不包含无效字符
        if (result_message.find('\0') != std::string::npos) {
            result_message = "Upgrade result: " + upgrade_result;
        }
        
        const std::string task_id_for_log = task_id_compact.empty() ? std::string("<none>") : task_id_compact;
        Log("INFO", "Processing upgrade result - Channel: " + std::to_string(upgrade_channel) +
            ", Task Code: " + task_id_for_log + ", Result: " + upgrade_result + ", Version: " + firmware_version);
        // 将固件版本写回devices表（仅更新该字段）
        {
            auto upd_res = db_client_->UpdateDeviceFirmwareVersion(device_id, firmware_version);
            if (!upd_res.success) {
                Log("WARN", "UpdateDeviceFirmwareVersion failed for device: " + device_id + ", err: " + upd_res.error_message);
            } else {
                Log("DEBUG", "Updated device.firmware_version to '" + firmware_version + "' for device: " + device_id);
                if (cache_client_) {
                    cache_client_->InvalidateDevice(device_id);
                }
            }
        }
        if (skip_task_flow) {
            Log("INFO", "Local/USB upgrade result processed without task binding for device: " + device_id);
            return {true, "", 0x00};
        }

        // 通过task_code查询对应的task_id
        auto task_id_result = db_client_->GetUpgradeTaskIdByCode(task_id);
        if (!task_id_result.first.success) {
            Log("ERROR", "Failed to get task_id by task_code " + task_id + ": " + task_id_result.first.error_message);
            return {false, "Invalid task_code", 0x03}; // 报文不正确
        }
        
        if (task_id_result.second.empty()) {
            Log("ERROR", "Task_code " + task_id + " not found in database");
            return {false, "Task not found", 0x03}; // 报文不正确
        }
        
        std::string actual_task_id = task_id_result.second;
        Log("DEBUG", "Found task_id: " + actual_task_id + " for task_code: " + task_id);
        
        auto db_result = db_client_->FinalizeDeviceUpgradeTask(device_id, actual_task_id, status, result_message);
        if (!db_result.success) {
            Log("ERROR", "Failed to finalize upgrade task for device " + device_id + ": " + db_result.error_message);
            return {false, db_result.error_message, 0x01}; // 失败
        }
        // 防止重复推送：当前设备已上报结果，立即将其任务缓存置为“无任务”
        if (cache_client_) {
            try {
                cache_client_->SetUpgradeTask(device_id, std::nullopt, 30);
                Log("DEBUG", "Cleared upgrade task cache for device after result: " + device_id);
            } catch (const std::exception& e) {
                Log("WARN", std::string("Failed to clear device upgrade task cache: ") + e.what());
            }
        }
        
        // 检查并更新升级任务的整体状态
        auto task_status_result = db_client_->CheckAndUpdateUpgradeTaskStatus(actual_task_id);
        if (!task_status_result.success) {
            Log("WARN", "Failed to check/update upgrade task status for task " + actual_task_id + ": " + task_status_result.error_message);
            // 这里不返回错误，因为设备的升级记录已经成功保存了
        } else {
            Log("INFO", "Upgrade task status check result: " + task_status_result.error_message); // error_message字段这里用作消息传递
            
            // 如果任务已经完成，清理相关缓存
            if (task_status_result.error_message.find("marked as completed") != std::string::npos) {
                Log("INFO", "Upgrade task " + actual_task_id + " has been completed, clearing related caches");
                if (cache_client_) {
                    try {
                        cache_client_->ClearAllUpgradeLocks();
                        Log("DEBUG", "Cleared all upgrade locks after task completion");
                    } catch (const std::exception& e) {
                        Log("WARN", "Failed to clear upgrade locks: " + std::string(e.what()));
                    }
                }
            }
        }
        
        Log("INFO", "Successfully processed upgrade result for device: " + device_id + ", result: " + upgrade_result);
        return {true, "", 0x00}; // 成功
        
    } catch (const std::exception& e) {
        Log("ERROR", "Exception in ProcessUpgradeResultReport: " + std::string(e.what()));
        return {false, e.what(), 0x01}; // 失败
    }
}

void UpgradeServiceImpl::Log(const std::string& level, const std::string& message) const {
    Utils::Logger::Instance().Log(level, message, "UpgradeService");
}
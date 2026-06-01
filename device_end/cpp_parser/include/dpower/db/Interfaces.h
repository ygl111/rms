#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <chrono>
#include <optional>
#include <json.hpp>

using Json = nlohmann::json;

namespace DPower {
namespace DB {

struct DPowerDBResult {
    bool        success { false };
    std::string error_message;
};

struct DPowerDeviceRecord {
    std::string device_id;
    int         model_id   { 0 };
    std::string model_name;
    int         device_type { 0 };
    std::string firmware_version;
    std::string hardware_version;
    std::string main_software_version;
    std::string currency_library_version; // 改名，币种库版本
    std::string suffix_marker;            // 改名，设备后缀标记
    std::string branch_info;
    std::string online_status = "offline";
    std::chrono::system_clock::time_point last_online_time;
    std::string ip_endpoint;              // 新增，设备IP和端口
    std::string auth_code;
    bool        activated { false };
    std::chrono::system_clock::time_point created_at;
    std::chrono::system_clock::time_point updated_at;
    Json        extra_data;
    uint32_t    maintenance_threshold { 0 }; // 设备维护阈值
};

enum class DPowerUpgradeStatus {
    Pending,
    InProgress,
    Completed,
    Failed
};

struct DPowerUpgradeTask {
    // 任务基本信息
    std::string task_id;
    std::string task_code;
    int         model_id = 0;  // 新增：设备型号ID
    std::string status = "active";  // 新增：任务状态 (active/cancelled/completed)
    std::chrono::system_clock::time_point start_date;  // 新增：计划开始日期
    std::chrono::system_clock::time_point end_date;    // 新增：计划结束日期
    bool        has_schedule_window = false;           // 新增：是否存在计划时间窗口
    
    // 设备分配状态（来自 device_mapping_upgrade_task 表）
    int         device_task_status = 0;  // 新增：0=未开始，1=已开始，2=已完成，3=失败
    bool        confirm_upgrade = true;  // 新增：确认是否需要升级，默认true
    
    // 升级配置
    bool        force_upgrade = false;
    float       time_arrange_start = 0.0;
    float       time_arrange_end = 23.59;
    uint8_t     module_type = 0;

    // 固件信息
    std::string firmware_id;
    std::string firmware_name;
    std::string firmware_version;
    long long   file_size = 0;
    std::string md5_hash;
    std::string storage_path;  // 重命名：从 ftp_dir 改为 storage_path，更符合数据库字段名

    // FTP/下载信息（从 storage_path 解析或配置生成）
    std::string ftp_host;
    int         ftp_port = 21;
    std::string ftp_dir;
    std::string download_url; // 完整的下载URL（由 storage_path 生成）
};

struct BanknoteCurrencyStat {
    std::string count_id;
    std::string currency_code;
    double      value;           // 单张钞票面值（元）
    uint16_t    note_count;
    double      amount;          // 金额（元）
};

struct BanknoteDetailRecord {
    std::string count_id;
    uint32_t    seq { 0 };       // 同一次count内的明细序号，从1开始
    std::string currency_code;
    double      note_value;      // 钞票面值（元）
    uint8_t     note_version;
    uint8_t     error_group;     // 报错组别
    uint16_t    error_type;      // 报错类型(新协议为uint16)
    std::string error_code;      // 报错码字符串
    std::string serial_number;
    uint8_t     stacker;         // 出钞口编号
};

struct DeviceWorkTimeDetail {
    std::string device_id;
    std::chrono::system_clock::time_point event_time_utc;
    uint32_t duration_ms {0};
    std::string detail_id;
};

struct BanknoteCountReport {
    std::string id;
    std::string device_id;
    std::string institution_id;      // 冗余字段：所属机构ID
    std::string device_identifier;   // 冗余字段：设备业务编号
    std::string institution_name;    // 冗余字段：机构名称
    std::string institution_code;    // 冗余字段：机构编码
    uint8_t     work_mode;
    uint8_t     business_mode;
    uint8_t     accumulate_flag;
    std::chrono::system_clock::time_point count_time;
    uint16_t    total_passed_count;
    uint16_t    failed_count;    // 过钞失败数量
    double      total_amount;    // 总金额（元）
    uint8_t     currency_count;
    std::vector<BanknoteCurrencyStat> currency_stats;
    std::vector<BanknoteDetailRecord> details;
};

struct DPowerFaultRecord {
    std::string id;                    // 主键ID (UUID)
    std::string device_id;             // 外键，故障设备ID
    std::string fault_code;            // 故障代码（事件码）
    std::string description;           // 故障描述(事件内容)
    std::string status;                // 处理状态 (unprocessed/processing/processed)
    std::chrono::system_clock::time_point fault_time;  // 故障发生时间（事件时间）
    Json extra_data;                   // 预留扩展字段
    int fault_level;                   // 故障等级(事件等级)
};

class DPowerDatabaseClient {
public:
    virtual ~DPowerDatabaseClient() = default;
    virtual DPowerDBResult Connect(const std::string& connection_uri, const std::string& username = "", const std::string& password = "") = 0;
    virtual void Disconnect() = 0;
    virtual bool IsConnected() const = 0;
    virtual bool Ping() = 0;
    virtual DPowerDBResult GetDeviceById(const std::string& device_id, DPowerDeviceRecord& out_record) = 0;
    virtual DPowerDBResult UpdateDevice(const DPowerDeviceRecord& record) = 0;
    virtual DPowerDBResult UpdateDeviceFirmwareVersion(const std::string& device_id, const std::string& firmware_version) = 0;
    virtual DPowerDBResult UpdateDeviceAuthCode(const std::string& device_id, const std::string& auth_code) = 0;
    virtual DPowerDBResult UpdateDeviceStatus(const std::string& device_id, const std::string& status, const std::string& ip_endpoint, bool update_ip_endpoint = true) = 0;
    virtual std::pair<DPowerDBResult, std::vector<std::pair<std::string, std::chrono::system_clock::time_point>>> GetOnlineDevices() = 0;
    virtual std::pair<DPowerDBResult, std::optional<DPowerUpgradeTask>> GetPendingUpgradeTask(const std::string& device_id, const std::string& ftp_host = "192.168.12.132", int ftp_port = 21) = 0;
    virtual std::pair<DPowerDBResult, std::string> GetUpgradeTaskIdByCode(const std::string& task_code) = 0;
    virtual DPowerDBResult FinalizeDeviceUpgradeTask(const std::string& device_id, const std::string& task_id, DPowerUpgradeStatus status, const std::string& result_message) = 0;
    // 统计与更新（为不同版本兼容，提供细粒度统计接口）
    virtual long long GetUpgradeTaskDevicesCount(const std::string& task_id) = 0;            // 需升级设备数（confirm_upgrade=1）
    virtual long long GetUpgradeTaskCompletionCount(const std::string& task_id) = 0;         // 终态完成设备数（status IN (1,2)）
    virtual DPowerDBResult UpdateUpgradeTaskStatus(const std::string& task_id, DPowerUpgradeStatus status) = 0; // 将任务置为 completed/active 等
    virtual DPowerDBResult CheckAndUpdateUpgradeTaskStatus(const std::string& task_id) = 0;  // 便捷接口：统计并在全部完成时置 completed
    virtual DPowerDBResult SaveBanknoteReport(const BanknoteCountReport& report) = 0;
    virtual DPowerDBResult InsertDeviceWorkTimeDetail(DeviceWorkTimeDetail& detail) = 0;
    virtual DPowerDBResult InsertFaultRecord(const DPowerFaultRecord& record) = 0;
    virtual long long GetDeviceCount() = 0;
    virtual long long GetUpgradeTaskCount() = 0;
};

class DPowerDatabaseFactory {
public:
    virtual ~DPowerDatabaseFactory() = default;
    virtual std::unique_ptr<DPowerDatabaseClient> Create() = 0;
};
std::unique_ptr<DPowerDatabaseFactory> CreateMySqlDatabaseFactory();

} // namespace DB
} // namespace DPower

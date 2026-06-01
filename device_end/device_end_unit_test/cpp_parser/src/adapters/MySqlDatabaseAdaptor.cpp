#include "dpower/db/Interfaces.h"
#include "logic/utils/MessageUtils.h"
#include <mysql/mysql.h>
#include <mysql/mysql_com.h>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <ctime>
#include <memory>
#include <unordered_map>
#include <vector>
#include <mutex>
#include <thread>
#include <cctype>
#include <cstdlib>
#include "logic/utils/MessageUtils.h"

namespace DPower::DB {

// PreparedStatement parameter types
enum class ParamType {
    STRING,
    INT,
    UINT,
    LONG_LONG,
    DOUBLE,
    TIME_POINT
};

// PreparedStatement parameter struct
struct PreparedParam {
    ParamType type;
    std::string str_value;
    int int_value;
    unsigned int uint_value;
    long long long_value;
    double double_value;
    std::chrono::system_clock::time_point time_value;
    
    PreparedParam(const std::string& value) : type(ParamType::STRING), str_value(value) {}
    PreparedParam(int value) : type(ParamType::INT), int_value(value) {}
    PreparedParam(unsigned int value) : type(ParamType::UINT), uint_value(value) {}
    PreparedParam(long long value) : type(ParamType::LONG_LONG), long_value(value) {}
    PreparedParam(double value) : type(ParamType::DOUBLE), double_value(value) {}
    PreparedParam(const std::chrono::system_clock::time_point& value) : type(ParamType::TIME_POINT), time_value(value) {}
};

// PreparedStatement execution result
struct PreparedResult {
    bool success;
    std::string error_message;
    MYSQL_RES* result;
    
    PreparedResult(bool s, const std::string& err = "") : success(s), error_message(err), result(nullptr) {}
    PreparedResult(bool s, MYSQL_RES* res) : success(s), error_message(""), result(res) {}
};

// PreparedStatement helper class
class PreparedStatement {
private:
    MYSQL* conn_;
    MYSQL_STMT* stmt_;
    std::vector<MYSQL_BIND> binds_;
    std::vector<std::vector<char>> string_buffers_; // For string and time data
    std::vector<unsigned long> lengths_;
    std::vector<char> is_null_values_; // kept for potential future NULLs (not used now)
    
public:
    PreparedStatement(MYSQL* conn) : conn_(conn), stmt_(nullptr) {}
    
    ~PreparedStatement() {
        if (stmt_) {
            mysql_stmt_close(stmt_);
        }
    }
    
    bool Prepare(const std::string& sql) {
        stmt_ = mysql_stmt_init(conn_);
        if (!stmt_) {
            return false;
        }
        
        if (mysql_stmt_prepare(stmt_, sql.c_str(), sql.length()) != 0) {
            // Provide error context
            std::cerr << "mysql_stmt_prepare failed: " << mysql_stmt_error(stmt_) << std::endl;
            mysql_stmt_close(stmt_);
            stmt_ = nullptr;
            return false;
        }
        
        return true;
    }
    
    bool BindParams(const std::vector<PreparedParam>& params) {
        if (!stmt_) return false;
        
        binds_.assign(params.size(), MYSQL_BIND{});
        string_buffers_.assign(params.size(), std::vector<char>());
        lengths_.assign(params.size(), 0);
    is_null_values_.assign(params.size(), 0);

        for (size_t i = 0; i < params.size(); ++i) {
            MYSQL_BIND& bind = binds_[i];
            
            switch (params[i].type) {
                case ParamType::STRING: {
                    string_buffers_[i].assign(params[i].str_value.begin(), params[i].str_value.end());
                    bind.buffer_type = MYSQL_TYPE_STRING;
                    bind.buffer = string_buffers_[i].data();
                    bind.buffer_length = string_buffers_[i].size();
                    // *** CRITICAL FIX ***
                    // The `length` member must point to the actual data length for string types.
                    lengths_[i] = string_buffers_[i].size();
                    bind.length = &lengths_[i];
                    break;
                }
                case ParamType::INT: {
                    bind.buffer_type = MYSQL_TYPE_LONG;
                    bind.buffer = const_cast<int*>(&params[i].int_value);
                    break;
                }
                case ParamType::UINT: {
                    bind.buffer_type = MYSQL_TYPE_LONG;
                    bind.buffer = const_cast<unsigned int*>(&params[i].uint_value);
                    bind.is_unsigned = 1;
                    break;
                }
                case ParamType::LONG_LONG: {
                    bind.buffer_type = MYSQL_TYPE_LONGLONG;
                    bind.buffer = const_cast<long long*>(&params[i].long_value);
                    break;
                }
                case ParamType::DOUBLE: {
                    bind.buffer_type = MYSQL_TYPE_DOUBLE;
                    bind.buffer = const_cast<double*>(&params[i].double_value);
                    break;
                }
                case ParamType::TIME_POINT: {
                    std::time_t time = std::chrono::system_clock::to_time_t(params[i].time_value);
                    std::tm* tm = std::localtime(&time);
                    
                    MYSQL_TIME mysql_time;
                    mysql_time.year = tm->tm_year + 1900;
                    mysql_time.month = tm->tm_mon + 1;
                    mysql_time.day = tm->tm_mday;
                    mysql_time.hour = tm->tm_hour;
                    mysql_time.minute = tm->tm_min;
                    mysql_time.second = tm->tm_sec;
                    mysql_time.second_part = 0;
                    mysql_time.neg = 0;
                    mysql_time.time_type = MYSQL_TIMESTAMP_DATETIME;
                    
                    string_buffers_[i].resize(sizeof(MYSQL_TIME));
                    memcpy(string_buffers_[i].data(), &mysql_time, sizeof(MYSQL_TIME));
                    
                    bind.buffer_type = MYSQL_TYPE_DATETIME;
                    bind.buffer = string_buffers_[i].data();
                    break;
                }
            }
            // 输入参数不使用 NULL 指示器，避免类型不匹配导致的不确定行为
            bind.is_null = nullptr;
        }
        
        return mysql_stmt_bind_param(stmt_, binds_.data()) == 0;
    }
    
    bool Execute() {
        if (!stmt_) return false;
        return mysql_stmt_execute(stmt_) == 0;
    }
    
    PreparedResult ExecuteQuery() {
        if (!stmt_) return PreparedResult(false, "Statement not prepared");
        if (mysql_stmt_execute(stmt_) != 0) {
            return PreparedResult(false, mysql_stmt_error(stmt_));
        }
        
    MYSQL_RES* result = mysql_stmt_result_metadata(stmt_);
    // 对于非查询语句，result 可能为 nullptr，这是正常情况
    return PreparedResult(true, result);
    }
    
    MYSQL_STMT* GetStmt() const { return stmt_; }
};

// Helper function to convert C++ enum to database string
static std::string UpgradeStatusToString(DPowerUpgradeStatus status) {
    switch (status) {
        case DPowerUpgradeStatus::Completed: return "success";
        case DPowerUpgradeStatus::Failed:    return "failed";
        case DPowerUpgradeStatus::InProgress:return "processing";
        case DPowerUpgradeStatus::Pending:   return "pending";
        default:                             return "cancelled"; // Default case
    }
}

class MySqlClient : public DPowerDatabaseClient {
public:
    MySqlClient() : conn_(nullptr) {}
    ~MySqlClient() override { Disconnect(); }

    /* Connection */
    DPowerDBResult Connect(const std::string& uri,
                           const std::string& user,
                           const std::string& password) override {
        // 保存连接参数；不立即创建全局 conn_，改为按线程延迟创建
        {
            std::lock_guard<std::mutex> lk(conns_mutex_);
            uri_ = uri; user_ = user; password_ = password;
        }
        // 读取环境变量开关
        auto getenv_bool = [](const char* name, bool defVal) -> bool {
            const char* v = std::getenv(name);
            if (!v) return defVal;
            if (v[0] == '\0') return defVal;
            char c = static_cast<char>(std::tolower(static_cast<unsigned char>(v[0])));
            return (c == '1' || c == 'y' || c == 't');
        };
        per_thread_mode_ = getenv_bool("DP_DB_PER_THREAD", true);
        db_debug_enabled_ = getenv_bool("DP_DB_DEBUG", false);
        // 为当前线程建立连接以尽早发现问题
        if (!ensureConnection()) return {false, "Failed to open thread-local DB connection"};
        return {true, ""};
    }

    void Disconnect() override {
        // 关闭所有线程连接
        std::lock_guard<std::mutex> lk(conns_mutex_);
        for (auto* c : all_conns_) { if (c) mysql_close(c); }
        all_conns_.clear();
        tls_conn_ = nullptr;
        if (conn_) { mysql_close(conn_); conn_ = nullptr; }
    }
    bool IsConnected() const override {
        // 在每线程模式下，为当前线程确保连接已建立
        if (per_thread_mode_) {
            return const_cast<MySqlClient*>(this)->ensureConnection();
        }
        // 单连接模式：若已有连接则检测健康，否则尝试建立
        if (conn_) {
            if (mysql_ping(conn_) == 0) return true;
        }
        return const_cast<MySqlClient*>(this)->ensureConnection();
    }
    
    bool Ping() override { return ensureConnection(); }

    /* Device operations */
    DPowerDBResult GetDeviceById(const std::string& device_id_str, DPowerDeviceRecord& out) override {
    
        if (!ensureConnection()) {
            return {false, "Database connection is not available."};
        }
        if (db_debug_enabled_) {
            std::cout << "[DB DEBUG] MySqlClient::GetDeviceById query device_id='" << device_id_str << "'" << std::endl;
        }

        const std::string sql = "SELECT id, device_id, device_type, authentication_code, model_id, online_status, firmware_version, hardware_version, main_software_version, currency_library_version, suffix_marker, ip_endpoint, last_online_time FROM devices WHERE device_id = ? AND is_deleted = 0 LIMIT 1";
        
        PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql)) {
            return {false, "Failed to prepare statement: " + std::string(mysql_error(currentConn()))};
        }
        
        if (!stmt.BindParams({device_id_str})) {
            return {false, "Failed to bind parameters: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        
        PreparedResult result = stmt.ExecuteQuery();
        if (!result.success) {
            return {false, result.error_message};
        }
        
        if (!result.result) {
            out = {};
            return {true, ""};
        }
        
        // Bind result columns
        MYSQL_BIND bind[13];
        memset(bind, 0, sizeof(bind));
        
        char id_buffer[37], device_id_buffer[37], auth_code_buffer[64], online_status_buffer[10], firmware_version_buffer[64], 
             hardware_version_buffer[513], main_software_version_buffer[1025], currency_library_version_buffer[2049], suffix_marker_buffer[10],
             ip_endpoint_buffer[256];
        MYSQL_TIME last_online_time_mysql;
        int device_type, model_id;
        unsigned long id_length, device_id_length, auth_code_length, online_status_length, firmware_version_length,
                      hardware_version_length, main_software_version_length, currency_library_version_length, suffix_marker_length,
                      ip_endpoint_length;
        bool id_is_null, device_id_is_null, auth_code_is_null, online_status_is_null, firmware_version_is_null,
                hardware_version_is_null, main_software_version_is_null, currency_library_version_is_null, suffix_marker_is_null,
                ip_endpoint_is_null, last_online_time_is_null;
        
        bind[0].buffer_type = MYSQL_TYPE_STRING; bind[0].buffer = id_buffer; bind[0].buffer_length = sizeof(id_buffer); bind[0].length = &id_length; bind[0].is_null = &id_is_null;
        bind[1].buffer_type = MYSQL_TYPE_STRING; bind[1].buffer = device_id_buffer; bind[1].buffer_length = sizeof(device_id_buffer); bind[1].length = &device_id_length; bind[1].is_null = &device_id_is_null;
        bind[2].buffer_type = MYSQL_TYPE_LONG; bind[2].buffer = &device_type;
        bind[3].buffer_type = MYSQL_TYPE_STRING; bind[3].buffer = auth_code_buffer; bind[3].buffer_length = sizeof(auth_code_buffer); bind[3].length = &auth_code_length; bind[3].is_null = &auth_code_is_null;
        bind[4].buffer_type = MYSQL_TYPE_LONG; bind[4].buffer = &model_id;
        bind[5].buffer_type = MYSQL_TYPE_STRING; bind[5].buffer = online_status_buffer; bind[5].buffer_length = sizeof(online_status_buffer); bind[5].length = &online_status_length; bind[5].is_null = &online_status_is_null;
        bind[6].buffer_type = MYSQL_TYPE_STRING; bind[6].buffer = firmware_version_buffer; bind[6].buffer_length = sizeof(firmware_version_buffer); bind[6].length = &firmware_version_length; bind[6].is_null = &firmware_version_is_null;
        bind[7].buffer_type = MYSQL_TYPE_STRING; bind[7].buffer = hardware_version_buffer; bind[7].buffer_length = sizeof(hardware_version_buffer); bind[7].length = &hardware_version_length; bind[7].is_null = &hardware_version_is_null;
        bind[8].buffer_type = MYSQL_TYPE_STRING; bind[8].buffer = main_software_version_buffer; bind[8].buffer_length = sizeof(main_software_version_buffer); bind[8].length = &main_software_version_length; bind[8].is_null = &main_software_version_is_null;
        bind[9].buffer_type = MYSQL_TYPE_STRING; bind[9].buffer = currency_library_version_buffer; bind[9].buffer_length = sizeof(currency_library_version_buffer); bind[9].length = &currency_library_version_length; bind[9].is_null = &currency_library_version_is_null;
        bind[10].buffer_type = MYSQL_TYPE_STRING; bind[10].buffer = suffix_marker_buffer; bind[10].buffer_length = sizeof(suffix_marker_buffer); bind[10].length = &suffix_marker_length; bind[10].is_null = &suffix_marker_is_null;
        bind[11].buffer_type = MYSQL_TYPE_STRING; bind[11].buffer = ip_endpoint_buffer; bind[11].buffer_length = sizeof(ip_endpoint_buffer); bind[11].length = &ip_endpoint_length; bind[11].is_null = &ip_endpoint_is_null;
        bind[12].buffer_type = MYSQL_TYPE_DATETIME; bind[12].buffer = &last_online_time_mysql; bind[12].is_null = &last_online_time_is_null;
        
        if (mysql_stmt_bind_result(stmt.GetStmt(), bind) != 0) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return {false, "Failed to bind result: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        
        if (mysql_stmt_fetch(stmt.GetStmt()) != 0) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            out = {};
            return {true, ""}; // No record found is not an error
        }
        
        // Populate output struct with safe string construction
        auto safe_string = [](const char* buffer, unsigned long length, size_t max_len, bool is_null) -> std::string {
            if (is_null) {
                return "";
            }
            if (length > max_len) {
                // Log the issue but cap the length to prevent crash
                length = max_len;
            }
            if (length == 0 || !buffer) {
                return "";
            }
            return std::string(buffer, length);
        };
        
        out.device_id = safe_string(device_id_buffer, device_id_length, 64, device_id_is_null);
        out.device_type = device_type;
        out.auth_code = safe_string(auth_code_buffer, auth_code_length, 64, auth_code_is_null);
        out.model_id = model_id;
        out.online_status = safe_string(online_status_buffer, online_status_length, 10, online_status_is_null);
        out.firmware_version = safe_string(firmware_version_buffer, firmware_version_length, 64, firmware_version_is_null);
        out.hardware_version = safe_string(hardware_version_buffer, hardware_version_length, 512, hardware_version_is_null);
        out.main_software_version = safe_string(main_software_version_buffer, main_software_version_length, 1024, main_software_version_is_null);
        out.currency_library_version = safe_string(currency_library_version_buffer, currency_library_version_length, 2048, currency_library_version_is_null);
        out.suffix_marker = safe_string(suffix_marker_buffer, suffix_marker_length, 10, suffix_marker_is_null);
        out.ip_endpoint = safe_string(ip_endpoint_buffer, ip_endpoint_length, 255, ip_endpoint_is_null);
        
        // Convert MYSQL_TIME to chrono::system_clock::time_point
        if (last_online_time_mysql.year != 0) {
            std::tm tm = {};
            tm.tm_year = last_online_time_mysql.year - 1900;
            tm.tm_mon = last_online_time_mysql.month - 1;
            tm.tm_mday = last_online_time_mysql.day;
            tm.tm_hour = last_online_time_mysql.hour;
            tm.tm_min = last_online_time_mysql.minute;
            tm.tm_sec = last_online_time_mysql.second;
            std::time_t time = std::mktime(&tm);
            out.last_online_time = std::chrono::system_clock::from_time_t(time);
        }
        
    if (result.result) mysql_free_result(result.result);
    mysql_stmt_free_result(stmt.GetStmt());
        
        // Get model name in a separate query
        if(out.model_id > 0){
            const std::string model_sql = "SELECT model_name FROM device_mapping_model WHERE id = ? AND is_deleted = 0";
            PreparedStatement model_stmt(currentConn());
            if (model_stmt.Prepare(model_sql) && model_stmt.BindParams({out.model_id})) {
                PreparedResult model_result = model_stmt.ExecuteQuery();
                if (model_result.success && model_result.result) {
                    MYSQL_BIND model_bind; memset(&model_bind, 0, sizeof(model_bind));
                    char model_name_buffer[21]; unsigned long model_name_length;
                    model_bind.buffer_type = MYSQL_TYPE_STRING; model_bind.buffer = model_name_buffer; model_bind.buffer_length = sizeof(model_name_buffer); model_bind.length = &model_name_length;
                    if (mysql_stmt_bind_result(model_stmt.GetStmt(), &model_bind) == 0 && mysql_stmt_fetch(model_stmt.GetStmt()) == 0) {
                        // Safe string construction for model_name
                        if (model_name_length > 0 && model_name_length <= 20) {
                            out.model_name = std::string(model_name_buffer, model_name_length);
                        } else {
                            out.model_name = "";
                        }
                    }
                    if (model_result.result) mysql_free_result(model_result.result);
                    mysql_stmt_free_result(model_stmt.GetStmt());
                }
            }
        }
        
        return {true,""};
    }

    DPowerDBResult UpdateDevice(const DPowerDeviceRecord& rec) override {
        if (!ensureConnection()) return {false, "Database connection is not available."};
        
        const std::string sql = 
            "UPDATE devices SET "
            "device_type = ?, firmware_version = ?, "
            "currency_library_version = ?, hardware_version = ?, "
            "main_software_version = ?, suffix_marker = ?, "
            "updated_at = NOW() "
            "WHERE device_id = ? AND is_deleted = 0";
        
        PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql)) {
            return {false, "Failed to prepare statement: " + std::string(mysql_error(currentConn()))};
        }
        
        std::vector<PreparedParam> params = {
            rec.device_type,
            MessageUtils::NormalizeForDb(rec.firmware_version),
            MessageUtils::NormalizeForDb(rec.currency_library_version),
            MessageUtils::NormalizeForDb(rec.hardware_version),
            MessageUtils::NormalizeForDb(rec.main_software_version),
            MessageUtils::NormalizeForDb(rec.suffix_marker),
            MessageUtils::NormalizeForDb(rec.device_id)
        };

        if (db_debug_enabled_) {
            // 安全输出，避免无效UTF-8字符导致JSON异常
            auto safe_output = [](const std::string& s) -> std::string {
                if (MessageUtils::IsValidUtf8(s)) {
                    return s;
                } else {
                    // 转换为十六进制显示
                    std::ostringstream oss;
                    oss << "[HEX:";
                    for (unsigned char c : s) {
                        oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c);
                    }
                    oss << "]";
                    return oss.str();
                }
            };
            
            std::cout << "[DB DEBUG] UpdateDevice bind values: "
                      << "device_type=" << rec.device_type
                      << ", firmware='" << safe_output(MessageUtils::NormalizeForDb(rec.firmware_version)) << "'"
                      << ", currency='" << safe_output(MessageUtils::NormalizeForDb(rec.currency_library_version)) << "'"
                      << ", hardware='" << safe_output(MessageUtils::NormalizeForDb(rec.hardware_version)) << "'"
                      << ", main='" << safe_output(MessageUtils::NormalizeForDb(rec.main_software_version)) << "'"
                      << ", suffix='" << safe_output(MessageUtils::NormalizeForDb(rec.suffix_marker)) << "'"
                      << ", device_id='" << safe_output(MessageUtils::NormalizeForDb(rec.device_id)) << "'"
                      << std::endl;
        }
        
        if (!stmt.BindParams(params) || !stmt.Execute()) {
            return {false, "Failed to bind/execute statement: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        
        if (mysql_stmt_affected_rows(stmt.GetStmt()) == 0) {
            return {true, "Device with device_id " + rec.device_id + " not found or data unchanged."};
        }
        
        return {true,""};
    }

    // 新增：仅更新固件版本，避免修改其它字段
    DPowerDBResult UpdateDeviceFirmwareVersion(const std::string& device_id,
                                              const std::string& firmware_version) override {
        if (!ensureConnection()) return {false, "Database connection is not available."};
        const std::string sql = "UPDATE devices SET firmware_version = ?, updated_at = NOW() WHERE device_id = ? AND is_deleted = 0";
        PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql)) {
            return {false, "Failed to prepare statement: " + std::string(mysql_error(currentConn()))};
        }
    if (!stmt.BindParams({MessageUtils::NormalizeForDb(firmware_version), MessageUtils::NormalizeForDb(device_id)}) || !stmt.Execute()) {
            return {false, "Failed to bind/execute statement: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        return {true, ""};
    }

    DPowerDBResult UpdateDeviceAuthCode(const std::string& device_id, const std::string& code) override {
    if(!ensureConnection()) return {false,"not connected"};
        
        const std::string sql = "UPDATE devices SET authentication_code = ?, updated_at = NOW() WHERE device_id = ? AND is_deleted = 0";
        
        PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql)) {
            return {false, "Failed to prepare statement: " + std::string(mysql_error(currentConn()))};
        }
        
    if (!stmt.BindParams({code, MessageUtils::NormalizeForDb(device_id)}) || !stmt.Execute()) {
            return {false, "Failed to bind/execute statement: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        
        return {true,""};
    }

    DPowerDBResult SaveBanknoteReport(const BanknoteCountReport& report) override {
    
        if (!ensureConnection()) return {false, "Database connection is not available."};

        auto device_uuid_opt = getDeviceUUID(report.device_id);
        if (!device_uuid_opt) {
            return {false, "Device with device_id " + report.device_id + " not found."};
        }
        std::string device_uuid = *device_uuid_opt;

        if (mysql_query(currentConn(), "START TRANSACTION")) {
            return {false, "Failed to start transaction: " + std::string(mysql_error(currentConn()))};
        }

        // Generate a UUID for the report in the application to ensure consistency
        std::string report_uuid;
        if (mysql_query(currentConn(), "SELECT UUID()")) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to generate UUID: " + std::string(mysql_error(currentConn()))};
        }
        MYSQL_RES* res = mysql_store_result(currentConn());
        if (res) {
            MYSQL_ROW row = mysql_fetch_row(res);
            if (row && row[0]) report_uuid = row[0];
            mysql_free_result(res);
        }
        if (report_uuid.empty()) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Could not retrieve new UUID for report."};
        }
        
        // 1. Insert into banknote_counts
        const std::string insert_count_sql = 
            "INSERT INTO banknote_counts (id, device_id, work_mode, business_mode, accumulate_flag, count_time, total_passed_count, failed_count, total_amount, currency_count, created_at, is_deleted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), 0)";
        
    PreparedStatement count_stmt(currentConn());
        if (!count_stmt.Prepare(insert_count_sql)) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to prepare count statement: " + std::string(mysql_error(currentConn()))};
        }
        
        std::vector<PreparedParam> count_params = {
            report_uuid, device_uuid, report.work_mode, report.business_mode, 
            report.accumulate_flag, report.count_time, report.total_passed_count, 
            report.failed_count, report.total_amount, report.currency_count
        };
        
        if (!count_stmt.BindParams(count_params) || !count_stmt.Execute()) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to insert into banknote_counts: " + std::string(mysql_stmt_error(count_stmt.GetStmt()))};
        }

        // 2. Insert into banknote_count_currencies
        const std::string insert_currency_sql = 
            "INSERT INTO banknote_count_currencies (id, count_id, currency_code, value, note_count, amount, is_deleted) "
            "VALUES (UUID(), ?, ?, ?, ?, ?, 0)";
        
    PreparedStatement currency_stmt(currentConn());
        if (!currency_stmt.Prepare(insert_currency_sql)) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to prepare currency statement: " + std::string(mysql_error(currentConn()))};
        }
        
        for (const auto& stat : report.currency_stats) {
            if (!currency_stmt.BindParams({report_uuid, MessageUtils::NormalizeForDb(stat.currency_code), stat.value, stat.note_count, stat.amount}) || !currency_stmt.Execute()) {
                mysql_query(currentConn(), "ROLLBACK");
                return {false, "Failed to insert into banknote_count_currencies: " + std::string(mysql_stmt_error(currency_stmt.GetStmt()))};
            }
        }

        // 3. Insert into banknote_detailed_data
        const std::string insert_detail_sql = 
            "INSERT INTO banknote_detailed_data (id, count_id, currency_code, note_value, note_version, error_type, error_code, serial_number, stacker, is_deleted) "
            "VALUES (UUID(), ?, ?, ?, ?, ?, ?, ?, ?, 0)";
        
    PreparedStatement detail_stmt(currentConn());
        if (!detail_stmt.Prepare(insert_detail_sql)) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to prepare detail statement: " + std::string(mysql_error(currentConn()))};
        }
        
        for (const auto& detail : report.details) {
            if (!detail_stmt.BindParams({
                    report_uuid,
                    MessageUtils::NormalizeForDb(detail.currency_code),
                    detail.note_value,
                    detail.note_version, // 数值字段不做 Normalize
                    detail.error_type,
                    detail.error_code,
                    MessageUtils::NormalizeForDb(detail.serial_number),
                    detail.stacker // 数值字段不做 Normalize
                }) || !detail_stmt.Execute()) {
                mysql_query(currentConn(), "ROLLBACK");
                return {false, "Failed to insert into banknote_detailed_data: " + std::string(mysql_stmt_error(detail_stmt.GetStmt()))};
            }
        }

        if (mysql_query(currentConn(), "COMMIT")) {
            return {false, "Failed to commit transaction: " + std::string(mysql_error(currentConn()))};
        }

        return {true, ""};
    }

    std::pair<DPowerDBResult, std::optional<DPowerUpgradeTask>> GetPendingUpgradeTask(const std::string& device_id,
                                                                                      const std::string& ftp_host,
                                                                                      int ftp_port) override {
    
        if (!ensureConnection()) {
            return {{false, "Database connection is not available."}, std::nullopt};
        }
        auto device_uuid_opt = getDeviceUUID(device_id);
        if (!device_uuid_opt) {
            return {{true, "Device not found"}, std::nullopt};
        }
        std::string device_uuid = *device_uuid_opt;

        const std::string sql = 
            "SELECT "
            "  t.id, t.task_code, t.model_id, t.status, t.start_date, t.end_date, "
            "  t.time_arrange_start, t.time_arrange_end, "
            "  dmt.status as device_task_status, dmt.confirm_upgrade, "
            "  f.id as firmware_id, f.firmware_name, f.version, f.file_size, f.md5_hash, f.storage_path "
            "FROM device_mapping_upgrade_task AS dmt "
            "JOIN upgrade_tasks AS t ON dmt.task_id = t.id "
            "JOIN firmwares AS f ON t.firmware_id = f.id "
            "WHERE dmt.device_id = ? "
            "  AND dmt.is_deleted = 0 "
            "  AND dmt.confirm_upgrade = 1 "
            "  AND dmt.status = 0 "
            "  AND t.status = 'active' "
            "  AND t.is_deleted = 0 "
            "  AND NOW() BETWEEN t.start_date AND t.end_date "
            "LIMIT 1";

    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql) || !stmt.BindParams({device_uuid})) {
            return {{false, "Failed to prepare/bind statement"}, std::nullopt};
        }
        
        PreparedResult result = stmt.ExecuteQuery();
        if (!result.success || !result.result) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return {{!result.success, result.error_message}, std::nullopt};
        }
        
        // Bind all result columns
        MYSQL_BIND bind[16];
        memset(bind, 0, sizeof(bind));
        
        char id_buffer[37], task_code_buffer[33], status_buffer[20], firmware_id_buffer[37], 
             firmware_name_buffer[129], version_buffer[129], md5_hash_buffer[33], storage_path_buffer[256],
             start_date_buffer[20], end_date_buffer[20];
        int model_id, device_task_status, confirm_upgrade;
        long long file_size;
        float time_arrange_start, time_arrange_end;
        unsigned long lengths[16] = {0};
        
        bind[0].buffer_type = MYSQL_TYPE_STRING; bind[0].buffer = id_buffer; bind[0].buffer_length = sizeof(id_buffer); bind[0].length = &lengths[0];
        bind[1].buffer_type = MYSQL_TYPE_STRING; bind[1].buffer = task_code_buffer; bind[1].buffer_length = sizeof(task_code_buffer); bind[1].length = &lengths[1];
        bind[2].buffer_type = MYSQL_TYPE_LONG; bind[2].buffer = &model_id;
        bind[3].buffer_type = MYSQL_TYPE_STRING; bind[3].buffer = status_buffer; bind[3].buffer_length = sizeof(status_buffer); bind[3].length = &lengths[3];
        bind[4].buffer_type = MYSQL_TYPE_STRING; bind[4].buffer = start_date_buffer; bind[4].buffer_length = sizeof(start_date_buffer); bind[4].length = &lengths[4];
        bind[5].buffer_type = MYSQL_TYPE_STRING; bind[5].buffer = end_date_buffer; bind[5].buffer_length = sizeof(end_date_buffer); bind[5].length = &lengths[5];
        bind[6].buffer_type = MYSQL_TYPE_FLOAT; bind[6].buffer = &time_arrange_start;
        bind[7].buffer_type = MYSQL_TYPE_FLOAT; bind[7].buffer = &time_arrange_end;
        bind[8].buffer_type = MYSQL_TYPE_LONG; bind[8].buffer = &device_task_status;
        bind[9].buffer_type = MYSQL_TYPE_LONG; bind[9].buffer = &confirm_upgrade;
        bind[10].buffer_type = MYSQL_TYPE_STRING; bind[10].buffer = firmware_id_buffer; bind[10].buffer_length = sizeof(firmware_id_buffer); bind[10].length = &lengths[10];
        bind[11].buffer_type = MYSQL_TYPE_STRING; bind[11].buffer = firmware_name_buffer; bind[11].buffer_length = sizeof(firmware_name_buffer); bind[11].length = &lengths[11];
        bind[12].buffer_type = MYSQL_TYPE_STRING; bind[12].buffer = version_buffer; bind[12].buffer_length = sizeof(version_buffer); bind[12].length = &lengths[12];
        bind[13].buffer_type = MYSQL_TYPE_LONGLONG; bind[13].buffer = &file_size;
        bind[14].buffer_type = MYSQL_TYPE_STRING; bind[14].buffer = md5_hash_buffer; bind[14].buffer_length = sizeof(md5_hash_buffer); bind[14].length = &lengths[14];
        bind[15].buffer_type = MYSQL_TYPE_STRING; bind[15].buffer = storage_path_buffer; bind[15].buffer_length = sizeof(storage_path_buffer); bind[15].length = &lengths[15];
        
        if (mysql_stmt_bind_result(stmt.GetStmt(), bind) != 0) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return {{false, "Failed to bind result"}, std::nullopt};
        }
        
        if (mysql_stmt_fetch(stmt.GetStmt()) != 0) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return {{true, ""}, std::nullopt}; // No task found
        }
        
        DPowerUpgradeTask task;
        task.task_id = std::string(id_buffer, lengths[0]);
        task.task_code = std::string(task_code_buffer, lengths[1]);
        task.model_id = model_id;
        task.status = std::string(status_buffer, lengths[3]);
        
        std::tm tm = {};
        std::istringstream ss_start(std::string(start_date_buffer, lengths[4]));
        ss_start >> std::get_time(&tm, "%Y-%m-%d %H:%M:%S");
        task.start_date = std::chrono::system_clock::from_time_t(std::mktime(&tm));
        
        std::istringstream ss_end(std::string(end_date_buffer, lengths[5]));
        ss_end >> std::get_time(&tm, "%Y-%m-%d %H:%M:%S");
        task.end_date = std::chrono::system_clock::from_time_t(std::mktime(&tm));
        
        task.time_arrange_start = time_arrange_start;
        task.time_arrange_end = time_arrange_end;
        task.device_task_status = device_task_status;
        task.confirm_upgrade = (confirm_upgrade == 1);
        task.firmware_id = std::string(firmware_id_buffer, lengths[10]);
        task.firmware_name = std::string(firmware_name_buffer, lengths[11]);
        task.firmware_version = std::string(version_buffer, lengths[12]);
        task.file_size = file_size;
        task.md5_hash = std::string(md5_hash_buffer, lengths[14]);
        task.storage_path = std::string(storage_path_buffer, lengths[15]);
        
        task.force_upgrade = false;
        task.module_type = 0;
        task.ftp_host = ftp_host;
        task.ftp_port = ftp_port;
        task.ftp_dir = task.storage_path;
        task.download_url = task.storage_path;

    if (result.result) mysql_free_result(result.result);
    mysql_stmt_free_result(stmt.GetStmt());
        return {{true, ""}, task};
    }

    DPowerDBResult FinalizeDeviceUpgradeTask(const std::string& device_id, 
                                             const std::string& task_id, 
                                             DPowerUpgradeStatus status,
                                             const std::string& result_message) override {
    
        if (!ensureConnection()) return {false, "Database connection is not available."};

        auto device_uuid_opt = getDeviceUUID(device_id);
        if (!device_uuid_opt) {
            return {false, "Device with device_id " + device_id + " not found."};
        }
        std::string device_uuid = *device_uuid_opt;

        // 仅在升级“完成”(成功/失败)时记录 upgrade_records 并更新设备任务状态；
        // 对于 in_progress 等中间状态，不写入记录且不将状态计入完成统计。
        const bool is_terminal = (status == DPowerUpgradeStatus::Completed || status == DPowerUpgradeStatus::Failed);

        if (!is_terminal) {
            // 非终态，直接返回成功（相当于忽略，仅由终态上报触发统计与任务完结）
            return {true, ""};
        }

        if (mysql_query(currentConn(), "START TRANSACTION")) {
            return {false, "Failed to start transaction: " + std::string(mysql_error(currentConn()))};
        }

        // 1. Insert into upgrade_records（created_at 设置为对应任务的 created_at）
        const std::string insert_sql =
            "INSERT INTO upgrade_records (id, task_id, device_id, status, result_message, completed_at, created_at) "
            "VALUES (UUID(), ?, ?, ?, ?, NOW(), COALESCE((SELECT created_at FROM upgrade_tasks WHERE id = ?), NOW()))";
        PreparedStatement insert_stmt(currentConn());
        if (!insert_stmt.Prepare(insert_sql)
            || !insert_stmt.BindParams({task_id, device_uuid, UpgradeStatusToString(status), MessageUtils::NormalizeForDb(result_message), task_id})
            || !insert_stmt.Execute()) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to insert into upgrade_records: " + std::string(mysql_stmt_error(insert_stmt.GetStmt()))};
        }

        // 2. Update device_mapping_upgrade_task
        int new_db_status = (status == DPowerUpgradeStatus::Completed) ? 1 : 2; 
        const std::string update_sql = "UPDATE device_mapping_upgrade_task SET status = ? WHERE device_id = ? AND task_id = ?";
    PreparedStatement update_stmt(currentConn());
        if (!update_stmt.Prepare(update_sql) || !update_stmt.BindParams({new_db_status, device_uuid, task_id}) || !update_stmt.Execute()) {
            mysql_query(currentConn(), "ROLLBACK");
            return {false, "Failed to update device_mapping_upgrade_task: " + std::string(mysql_stmt_error(update_stmt.GetStmt()))};
        }

        if(mysql_query(currentConn(), "COMMIT")) {
            std::string err = mysql_error(currentConn());
            mysql_query(currentConn(), "ROLLBACK"); // Attempt to rollback on commit failure
            return {false, "Failed to commit transaction: " + err};
        }

        return {true, ""};
    }

    // 统计：需升级设备数（confirm_upgrade = 1）
    long long GetUpgradeTaskDevicesCount(const std::string& task_id) override {
    
        if (!ensureConnection()) return -1;
        const std::string sql = R"(
            SELECT COUNT(*)
            FROM device_mapping_upgrade_task
            WHERE task_id = ? AND is_deleted = 0 AND confirm_upgrade = 1
        )";
    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql) || !stmt.BindParams({task_id})) return -1;
    PreparedResult r = stmt.ExecuteQuery();
    if (!r.success) { mysql_stmt_free_result(stmt.GetStmt()); return -1; }
        long long cnt = 0; MYSQL_BIND b{}; b.buffer_type = MYSQL_TYPE_LONGLONG; b.buffer = &cnt;
    if (mysql_stmt_bind_result(stmt.GetStmt(), &b) != 0) { if (r.result) mysql_free_result(r.result); mysql_stmt_free_result(stmt.GetStmt()); return -1; }
    int fr = mysql_stmt_fetch(stmt.GetStmt()); if (r.result) mysql_free_result(r.result); mysql_stmt_free_result(stmt.GetStmt());
        return fr == 0 ? cnt : -1;
    }

    // 统计：已终态完成设备数（status IN (1,2) 且 confirm_upgrade = 1）
    long long GetUpgradeTaskCompletionCount(const std::string& task_id) override {
    
        if (!ensureConnection()) return -1;
        const std::string sql = R"(
            SELECT SUM(CASE WHEN status IN (1,2) THEN 1 ELSE 0 END)
            FROM device_mapping_upgrade_task
            WHERE task_id = ? AND is_deleted = 0 AND confirm_upgrade = 1
        )";
    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql) || !stmt.BindParams({task_id})) return -1;
    PreparedResult r = stmt.ExecuteQuery();
    if (!r.success) { mysql_stmt_free_result(stmt.GetStmt()); return -1; }
        long long cnt = 0; MYSQL_BIND b{}; b.buffer_type = MYSQL_TYPE_LONGLONG; b.buffer = &cnt;
    if (mysql_stmt_bind_result(stmt.GetStmt(), &b) != 0) { if (r.result) mysql_free_result(r.result); mysql_stmt_free_result(stmt.GetStmt()); return -1; }
    int fr = mysql_stmt_fetch(stmt.GetStmt()); if (r.result) mysql_free_result(r.result); mysql_stmt_free_result(stmt.GetStmt());
        return fr == 0 ? cnt : -1;
    }

    // 更新任务状态
    DPowerDBResult UpdateUpgradeTaskStatus(const std::string& task_id, DPowerUpgradeStatus status) override {
    
        if (!ensureConnection()) return {false, "Database connection is not available."};
        std::string status_str;
        switch (status) {
            case DPowerUpgradeStatus::Completed: status_str = "completed"; break;
            case DPowerUpgradeStatus::Pending:   status_str = "active";    break;
            case DPowerUpgradeStatus::InProgress:status_str = "active";    break;
            case DPowerUpgradeStatus::Failed:    status_str = "active";    break;
            default:                              status_str = "active";    break;
        }
        const std::string sql = "UPDATE upgrade_tasks SET status = ? WHERE id = ?";
    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql) || !stmt.BindParams({status_str, task_id}) || !stmt.Execute()) {
            return {false, "Failed to update upgrade_tasks: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        return {true, ""};
    }

    DPowerDBResult CheckAndUpdateUpgradeTaskStatus(const std::string& task_id) override {
    
        if (!ensureConnection()) return {false, "Database connection is not available."};

        // 查询当前任务是否所有设备都已完成升级
        const std::string check_sql = R"(
            SELECT 
                COUNT(*) as total_devices,
                SUM(CASE WHEN status IN (1, 2) THEN 1 ELSE 0 END) as completed_devices
            FROM device_mapping_upgrade_task 
            WHERE task_id = ? AND is_deleted = 0 AND confirm_upgrade = 1
        )";

    PreparedStatement check_stmt(currentConn());
        if (!check_stmt.Prepare(check_sql) || !check_stmt.BindParams({task_id})) {
            return {false, "Failed to prepare/bind check statement"};
        }
        PreparedResult qres = check_stmt.ExecuteQuery();
        if (!qres.success) {
            return {false, "Failed to check upgrade task status: " + qres.error_message};
        }

        // Bind and fetch the two aggregate columns
        long long total_devices_ll = 0;
        long long completed_devices_ll = 0;
        MYSQL_BIND rbind[2];
        memset(rbind, 0, sizeof(rbind));
        rbind[0].buffer_type = MYSQL_TYPE_LONGLONG; rbind[0].buffer = &total_devices_ll;
        rbind[1].buffer_type = MYSQL_TYPE_LONGLONG; rbind[1].buffer = &completed_devices_ll;
        if (mysql_stmt_bind_result(check_stmt.GetStmt(), rbind) != 0) {
            if (qres.result) mysql_free_result(qres.result);
            mysql_stmt_free_result(check_stmt.GetStmt());
            return {false, "Failed to bind check result: " + std::string(mysql_stmt_error(check_stmt.GetStmt()))};
        }
        int fetch_rc = mysql_stmt_fetch(check_stmt.GetStmt());
        if (fetch_rc != 0) {
            if (qres.result) mysql_free_result(qres.result);
            mysql_stmt_free_result(check_stmt.GetStmt());
            return {false, "No devices found or fetch failed for task_id: " + task_id};
        }
        if (qres.result) mysql_free_result(qres.result);
        mysql_stmt_free_result(check_stmt.GetStmt());

        int total_devices = static_cast<int>(total_devices_ll);
        int completed_devices = static_cast<int>(completed_devices_ll);

        // 如果所有设备都已完成(status = 1表示完成成功，status = 2表示完成但失败)
        if (total_devices > 0 && completed_devices >= total_devices) {
            // 更新升级任务状态为完成
            const std::string update_sql = "UPDATE upgrade_tasks SET status = 'completed' WHERE id = ? AND status = 'active'";
            
            PreparedStatement update_stmt(currentConn());
            if (!update_stmt.Prepare(update_sql) || !update_stmt.BindParams({task_id}) || !update_stmt.Execute()) {
                return {false, "Failed to update upgrade task status: " + std::string(mysql_stmt_error(update_stmt.GetStmt()))};
            }

            // 检查是否真的更新了任务状态
            if (mysql_affected_rows(currentConn()) > 0) {
                return {true, "Upgrade task " + task_id + " marked as completed (" + std::to_string(completed_devices) + "/" + std::to_string(total_devices) + " devices completed)"};
            } else {
                return {true, "Upgrade task " + task_id + " was already completed or not found"};
            }
        } else {
            return {true, "Upgrade task " + task_id + " still in progress (" + std::to_string(completed_devices) + "/" + std::to_string(total_devices) + " devices completed)"};
        }
    }

    DPowerDBResult UpdateDeviceStatus(const std::string& device_id,
                                      const std::string& status,
                                      const std::string& ip_endpoint,
                                      bool update_ip_endpoint) override {
    
        if (!ensureConnection()) return {false, "Database connection is not available."};
        
        std::string sql;
        std::vector<PreparedParam> params;
        // 统一裁剪 ip_endpoint，避免超过数据库字段长度（IPv6+端口最大约45）
        std::string clamped_ip = MessageUtils::NormalizeForDb(ip_endpoint);
        if (clamped_ip.size() > 45) {
            clamped_ip = clamped_ip.substr(0, 45);
        }
        
        // 只有当状态为"online"时才更新last_online_time
        if (status == "online") {
            if (update_ip_endpoint) {
                sql = "UPDATE devices SET online_status = ?, last_online_time = NOW(), ip_endpoint = ? WHERE device_id = ? AND is_deleted = 0";
                params = {status, clamped_ip, device_id};
            } else {
                sql = "UPDATE devices SET online_status = ?, last_online_time = NOW() WHERE device_id = ? AND is_deleted = 0";
                params = {status, device_id};
            }
        } else {
            // 当状态为"offline"或其他状态时，只更新online_status，不更新last_online_time
            if (update_ip_endpoint) {
                sql = "UPDATE devices SET online_status = ?, ip_endpoint = ? WHERE device_id = ? AND is_deleted = 0";
                params = {status, clamped_ip, device_id};
            } else {
                sql = "UPDATE devices SET online_status = ? WHERE device_id = ? AND is_deleted = 0";
                params = {status, device_id};
            }
        }
        
    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql) || !stmt.BindParams(params) || !stmt.Execute()) {
            return {false, "Failed to prepare/bind/execute statement: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        
        return {true, ""};
    }

    std::pair<DPowerDBResult, std::string> GetUpgradeTaskIdByCode(const std::string& task_code) override {
    
        if (!ensureConnection()) return {{false, "Database connection is not available."}, ""};

        const std::string sql = "SELECT id FROM upgrade_tasks WHERE task_code = ? AND is_deleted = 0 LIMIT 1";
        
    PreparedStatement stmt(currentConn());
    if (!stmt.Prepare(sql) || !stmt.BindParams({MessageUtils::NormalizeForDb(task_code)})) {
            return {{false, "Failed to prepare/bind statement"}, ""};
        }
        
        PreparedResult result = stmt.ExecuteQuery();
        if (!result.success || !result.result) {
             if (result.result) mysql_free_result(result.result);
             mysql_stmt_free_result(stmt.GetStmt());
            return {{!result.success, result.error_message}, ""};
        }
        
        MYSQL_BIND bind; memset(&bind, 0, sizeof(bind));
        char id_buffer[37]; unsigned long id_length;
        bind.buffer_type = MYSQL_TYPE_STRING; bind.buffer = id_buffer; bind.buffer_length = sizeof(id_buffer); bind.length = &id_length;
        
        if (mysql_stmt_bind_result(stmt.GetStmt(), &bind) != 0) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return {{false, "Failed to bind result"}, ""};
        }
        
        std::string task_uuid = "";
        if (mysql_stmt_fetch(stmt.GetStmt()) == 0) {
            task_uuid = std::string(id_buffer, id_length);
        }
        
        if (result.result) mysql_free_result(result.result);
        mysql_stmt_free_result(stmt.GetStmt());
        return {{true, ""}, task_uuid};
    }

    /* Other interfaces simplified */
    DPowerDBResult InsertFaultRecord(const DPowerFaultRecord& record) override {
    
        if (!ensureConnection()) return {false, "Database connection is not available."};

        auto device_uuid_opt = getDeviceUUID(record.device_id);
        if (!device_uuid_opt) {
            return {false, "Device with device_id " + record.device_id + " not found."};
        }
        std::string device_uuid = *device_uuid_opt;

        const std::string sql = 
            "INSERT INTO faults (id, device_id, fault_code, description, status, fault_time, extra_data, fault_level, created_at, is_deleted) "
            "VALUES (UUID(), ?, ?, ?, ?, ?, ?, ?, NOW(), 0)";
        
    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql)) {
            return {false, "Failed to prepare statement: " + std::string(mysql_error(currentConn()))};
        }
        
        // 将JSON对象转换为字符串
        std::string extra_data_json = record.extra_data.dump();
        
        std::vector<PreparedParam> params = {
            device_uuid,
            MessageUtils::NormalizeForDb(record.fault_code),
            MessageUtils::NormalizeForDb(record.description),
            MessageUtils::NormalizeForDb(record.status),
            record.fault_time,
            extra_data_json,
            record.fault_level
        };
        
        if (!stmt.BindParams(params) || !stmt.Execute()) {
            return {false, "Failed to bind/execute statement: " + std::string(mysql_stmt_error(stmt.GetStmt()))};
        }
        
        return {true, ""};
    }


    long long GetDeviceCount() override{ 
        
        if (!ensureConnection()) return -1;
        if (mysql_query(currentConn(),"SELECT COUNT(*) FROM devices WHERE is_deleted=0")) return 0;
        MYSQL_RES* r = mysql_store_result(currentConn());
        if(!r) return 0; 
        MYSQL_ROW row = mysql_fetch_row(r); 
        long long v = (row && row[0]) ? std::stoll(row[0]) : 0; 
        mysql_free_result(r); 
        return v; 
    }
    long long GetUpgradeTaskCount() override{ return 0; }

private:
    MYSQL* conn_;
    std::string uri_;
    std::string user_;
    std::string password_;
    mutable std::recursive_mutex conn_mutex_;

    // 每线程连接（TLS）与连接集合，用于逐步迁移到每线程一连接模型
    static thread_local MYSQL* tls_conn_;
    std::vector<MYSQL*> all_conns_;
    mutable std::mutex conns_mutex_;

    // 模式与调试开关
    bool per_thread_mode_ = true;
    bool db_debug_enabled_ = false;

    // 获取当前线程的连接指针（逐步替代直接使用 conn_）
    MYSQL* currentConn() const { return per_thread_mode_ ? (tls_conn_ ? tls_conn_ : conn_) : conn_; }

    // Helper to get the device UUID (primary key) from its business ID (e.g., "TEST03")
    std::optional<std::string> getDeviceUUID(const std::string& device_id_str) {
    if (!ensureConnection()) {
            return std::nullopt;
        }

        const std::string sql = "SELECT id FROM devices WHERE device_id = ? AND is_deleted = 0 LIMIT 1";
    PreparedStatement stmt(currentConn());
        if (!stmt.Prepare(sql) || !stmt.BindParams({device_id_str})) {
            return std::nullopt;
        }

        PreparedResult result = stmt.ExecuteQuery();
        if (!result.success || !result.result) {
            if(result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return std::nullopt;
        }

        MYSQL_BIND bind;
        memset(&bind, 0, sizeof(bind));
        char uuid_buffer[37];
        unsigned long uuid_length;
        bind.buffer_type = MYSQL_TYPE_STRING;
        bind.buffer = uuid_buffer;
        bind.buffer_length = sizeof(uuid_buffer);
        bind.length = &uuid_length;

        if (mysql_stmt_bind_result(stmt.GetStmt(), &bind) != 0) {
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return std::nullopt;
        }

        if (mysql_stmt_fetch(stmt.GetStmt()) == 0) {
            std::string uuid = std::string(uuid_buffer, uuid_length);
            if (result.result) mysql_free_result(result.result);
            mysql_stmt_free_result(stmt.GetStmt());
            return uuid;
        }

        if (result.result) mysql_free_result(result.result);
        mysql_stmt_free_result(stmt.GetStmt());
        return std::nullopt;
    }

    /**
     * @brief 确保数据库连接是活跃的。如果断开则尝试重连。
     * @return 如果连接最终是可用的，返回true，否则返回false。
     */
    bool ensureConnection() {
        // 单连接模式
        if (!per_thread_mode_) {
            if (conn_) {
                if (mysql_ping(conn_) == 0) return true;
                if (mysql_ping(conn_) == 0) return true; // 再试一次，触发可能的自动重连
                mysql_close(conn_); conn_ = nullptr;
            }
            if (uri_.empty()) return false;
            // 解析 URI
            std::string host = uri_;
            std::string db   = "rms";
            unsigned int port = 3306;
            try {
                size_t slash = uri_.find('/');
                if (slash != std::string::npos) { host = uri_.substr(0, slash); db = uri_.substr(slash + 1); }
                size_t colon = host.find(':');
                if (colon != std::string::npos) { port = std::stoi(host.substr(colon + 1)); host = host.substr(0, colon); }
            } catch (...) {}
            MYSQL* c = mysql_init(nullptr);
            if (!c) return false;
            bool reconnect = 1; mysql_options(c, MYSQL_OPT_RECONNECT, &reconnect);
            if (db_debug_enabled_) {
                std::cout << "[DB DEBUG] Connecting(single) host='" << host << "' port=" << port
                          << " user='" << user_ << "' db='" << db << "'" << std::endl;
            }
            if (!mysql_real_connect(c, host.c_str(), user_.c_str(), password_.c_str(), db.c_str(), port, nullptr, 0)) {
                std::cerr << "[DB ERROR] connect failed: " << mysql_error(c) << std::endl;
                mysql_close(c);
                return false;
            }
            if (mysql_set_character_set(c, "utf8mb4")) {
                std::cerr << "[DB ERROR] set charset failed: " << mysql_error(c) << std::endl;
                mysql_close(c);
                return false;
            }
            conn_ = c;
            return true;
        }

        // 每线程模式：1) 当前线程已连接且健康
        if (tls_conn_) {
            if (mysql_ping(tls_conn_) == 0) return true;
            if (mysql_ping(tls_conn_) == 0) return true; // 再试一次，触发可能的自动重连
            mysql_close(tls_conn_);
            tls_conn_ = nullptr;
        }

        // 2) 如果存在旧的单连接且健康，则复用并绑定给当前线程
        if (conn_) {
            if (mysql_ping(conn_) == 0) { tls_conn_ = conn_; return true; }
            mysql_close(conn_); conn_ = nullptr;
        }

        // 3) 创建新的线程专属连接
        if (uri_.empty()) return false; // 尚未 Connect 配置参数

        // 解析 URI
        std::string host = uri_;
        std::string db   = "rms";
        unsigned int port = 3306;
        try {
            size_t slash = uri_.find('/');
            if (slash != std::string::npos) { host = uri_.substr(0, slash); db = uri_.substr(slash + 1); }
            size_t colon = host.find(':');
            if (colon != std::string::npos) { port = std::stoi(host.substr(colon + 1)); host = host.substr(0, colon); }
        } catch (...) {}

        MYSQL* c = mysql_init(nullptr);
        if (!c) return false;
        bool reconnect = 1; mysql_options(c, MYSQL_OPT_RECONNECT, &reconnect);
        if (db_debug_enabled_) {
            std::cout << "[DB DEBUG] Connecting(thread) host='" << host << "' port=" << port
                      << " user='" << user_ << "' db='" << db << "'" << std::endl;
        }
        if (!mysql_real_connect(c, host.c_str(), user_.c_str(), password_.c_str(), db.c_str(), port, nullptr, 0)) {
            std::cerr << "[DB ERROR] connect failed: " << mysql_error(c) << std::endl;
            mysql_close(c);
            return false;
        }
        if (mysql_set_character_set(c, "utf8mb4")) {
            std::cerr << "[DB ERROR] set charset failed: " << mysql_error(c) << std::endl;
            mysql_close(c);
            return false;
        }
        {
            std::lock_guard<std::mutex> lk(conns_mutex_);
            all_conns_.push_back(c);
        }
        tls_conn_ = c;
        return true;
    }
};

class MySqlFactory : public DPowerDatabaseFactory {
public:
    std::unique_ptr<DPowerDatabaseClient> Create() override { 
        return std::make_unique<MySqlClient>(); 
    }
};

std::unique_ptr<DPowerDatabaseFactory> CreateMySqlDatabaseFactory(){
    return std::make_unique<MySqlFactory>();
}

} // namespace DPower::DB

// 定义 thread_local 静态成员
thread_local MYSQL* DPower::DB::MySqlClient::tls_conn_ = nullptr;

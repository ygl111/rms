#pragma once

#include <cstdint>
#include <string>

enum class LicenseState {
    Ok,
    OverLimit,
    Expired,
    Invalid
};

struct LicenseDecision {
    LicenseState state = LicenseState::Invalid;
    std::string reason;
    int max_devices = 0;
    std::int64_t exp = 0;
    std::string mac;

    bool deny_new_connections() const {
        return state != LicenseState::Ok;
    }

    bool disconnect_existing_connections() const {
        return state == LicenseState::Expired || state == LicenseState::Invalid;
    }
};

class LicenseGuard {
public:
    explicit LicenseGuard(int fallback_max_connections);

    LicenseDecision Evaluate(std::size_t current_connections) const;// 仅做极速整数比较

private:
    int fallback_max_connections_;
    bool is_valid_cache_ = false;
    int max_devices_cache_ = 0;
    std::int64_t exp_cache_ = 0;
    std::string cached_reason_ = "uninitialized";
    
    // 把原来复杂的 Evaluate 拆分为两个
    void InitializeCache(); // 构造时调用，做重量级校验
    std::string cached_mac_ = "";

};

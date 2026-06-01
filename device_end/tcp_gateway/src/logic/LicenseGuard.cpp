#include "logic/LicenseGuard.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#include <limits>

#include <openssl/bio.h>
#include <openssl/evp.h>
#include <openssl/pem.h>
#include <openssl/rsa.h>

#ifdef __linux__
#include <ifaddrs.h>
#include <net/if.h>
#include <netpacket/packet.h>
#endif

#include "json.hpp"
#include "logic/utils/Logger.h"

using json = nlohmann::json;

namespace {

constexpr const char* kEnvLicenseToken = "LICENSE_TOKEN";
constexpr const char* kEnvLicenseRequired = "LICENSE_REQUIRED";
constexpr const char* kEnvPublicKeyPem = "LICENSE_PUBLIC_KEY_PEM";
constexpr const char* kProjectLicenseFile = "config/license.env";

// Build-time vendor public key. Replace with your actual public key before release.
constexpr const char* kVendorPublicKeyPem =
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEA1RNE+5IlovrBBxYowhGf\n"
    "t5uE9uFv+siWhJzgxigooUA7a4Fort/EHK24BuPQjT71zwY+HkJ3iTh02PHKs2EH\n"
    "y7IVwVMqRn+ejkdVUwYQBulf8zmt97JG+yOVh25D7iHVwSupFxAXm5jiHG0gJZNY\n"
    "IjdltxPz0M0uhhFjZxMPhPTymsns6CfRSFJ9EFlq2TUsUFUTv/bJW2Kb9lcXhOCQ\n"
    "gg8dRMO2sN4DToiweQKE/vSo07EcXlMYXS85SecFcYQDsyHiSYrOy9Tt3Fab6yPZ\n"
    "ZlYo1/mvw39zIR2apONPXOP4v3eUK0qieN+BjEqevFd5TzFZSawvqCKdbyVqh3vD\n"
    "vo7VAf80JahkIH4XsozymvKvniVsk9y8qDQYrPgEwmBnQJl11uNrzVfGbfL6/3w9\n"
    "luqHkoRksxt1xJLJxOqpuPAqBMhwL9vD6S6GwsXQhqhcHDiwIEAg4hQGvobp8F74\n"
    "fld7FH9tdQmpePXghj40ZPONTiu7/cyYDYK/kcWVnpKBAgMBAAE=\n"
    "-----END PUBLIC KEY-----\n";

static std::string ToLower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return s;
}

static std::string Trim(std::string s) {
    auto not_space = [](unsigned char c) { return !std::isspace(c); };
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), not_space));
    s.erase(std::find_if(s.rbegin(), s.rend(), not_space).base(), s.end());
    return s;
}

static std::unordered_map<std::string, std::string> LoadLicenseFile(const std::string& path) {
    std::unordered_map<std::string, std::string> kv;
    std::ifstream in(path);
    if (!in.is_open()) {
        return kv;
    }

    std::string line;
    while (std::getline(in, line)) {
        line = Trim(line);
        if (line.empty() || line[0] == '#') {
            continue;
        }
        auto pos = line.find('=');
        if (pos == std::string::npos) {
            continue;
        }
        std::string key = Trim(line.substr(0, pos));
        std::string value = Trim(line.substr(pos + 1));
        if (!key.empty()) {
            kv[key] = value;
        }
    }

    return kv;
}

static const std::unordered_map<std::string, std::string>& GetProjectLicenseConfig() {
    static const std::unordered_map<std::string, std::string> cfg = []() {
        auto first = LoadLicenseFile(kProjectLicenseFile);
        if (!first.empty()) {
            return first;
        }
        // 如果工作目录是 build/，兼容从 build 目录启动
        auto second = LoadLicenseFile("../config/license.env");
        if (!second.empty()) {
            return second;
        }
        return std::unordered_map<std::string, std::string>{};
    }();
    return cfg;
}

static std::string GetRuntimeConfigValue(const char* name) {
    const char* env = std::getenv(name);
    if (env) {
        return std::string(env);
    }

    const auto& cfg = GetProjectLicenseConfig();
    auto it = cfg.find(name);
    if (it != cfg.end()) {
        return it->second;
    }

    return "";
}

static std::string NormalizeMac(const std::string& mac) {
    std::string out;
    out.reserve(mac.size());
    for (char c : mac) {
        if (c == '-' || c == ':') {
            out.push_back(':');
        } else if (!std::isspace(static_cast<unsigned char>(c))) {
            out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
        }
    }
    return out;
}

static bool GetEnvBool(const char* name, bool default_value) {
    const std::string v = GetRuntimeConfigValue(name);
    if (v.empty()) {
        return default_value;
    }
    std::string s = ToLower(v);
    return s == "1" || s == "true" || s == "yes" || s == "on";
}

static std::string GetEnvStr(const char* name) {
    return GetRuntimeConfigValue(name);
}

static std::vector<unsigned char> Base64UrlDecode(const std::string& input) {
    std::string b64 = input;
    std::replace(b64.begin(), b64.end(), '-', '+');
    std::replace(b64.begin(), b64.end(), '_', '/');
    while (b64.size() % 4 != 0) {
        b64.push_back('=');
    }

    std::vector<unsigned char> out((b64.size() * 3) / 4 + 4);
    int n = EVP_DecodeBlock(out.data(), reinterpret_cast<const unsigned char*>(b64.data()), static_cast<int>(b64.size()));
    if (n < 0) {
        return {};
    }

    int pad = 0;
    if (!b64.empty() && b64.back() == '=') pad++;
    if (b64.size() >= 2 && b64[b64.size() - 2] == '=') pad++;
    n -= pad;
    if (n < 0) n = 0;
    out.resize(static_cast<std::size_t>(n));
    return out;
}

static bool VerifySignatureRsaPssSha256(const std::string& payload, const std::vector<unsigned char>& sig, const std::string& pubkey_pem) {
    BIO* bio = BIO_new_mem_buf(pubkey_pem.data(), static_cast<int>(pubkey_pem.size()));
    if (!bio) {
        return false;
    }

    EVP_PKEY* pkey = PEM_read_bio_PUBKEY(bio, nullptr, nullptr, nullptr);
    BIO_free(bio);
    if (!pkey) {
        return false;
    }

    EVP_MD_CTX* mdctx = EVP_MD_CTX_new();
    if (!mdctx) {
        EVP_PKEY_free(pkey);
        return false;
    }

    EVP_PKEY_CTX* pkey_ctx = nullptr;
    if (EVP_DigestVerifyInit(mdctx, &pkey_ctx, EVP_sha256(), nullptr, pkey) != 1) {
        EVP_MD_CTX_free(mdctx);
        EVP_PKEY_free(pkey);
        return false;
    }

    if (EVP_PKEY_base_id(pkey) == EVP_PKEY_RSA) {
        if (EVP_PKEY_CTX_set_rsa_padding(pkey_ctx, RSA_PKCS1_PSS_PADDING) <= 0) {
            EVP_MD_CTX_free(mdctx);
            EVP_PKEY_free(pkey);
            return false;
        }
        if (EVP_PKEY_CTX_set_rsa_mgf1_md(pkey_ctx, EVP_sha256()) <= 0) {
            EVP_MD_CTX_free(mdctx);
            EVP_PKEY_free(pkey);
            return false;
        }
    }

    if (EVP_DigestVerifyUpdate(mdctx, payload.data(), payload.size()) != 1) {
        EVP_MD_CTX_free(mdctx);
        EVP_PKEY_free(pkey);
        return false;
    }

    int ok = EVP_DigestVerifyFinal(mdctx, sig.data(), sig.size());
    EVP_MD_CTX_free(mdctx);
    EVP_PKEY_free(pkey);
    return ok == 1;
}

static std::string GetPrimaryMacAddress() {
#ifdef __linux__
    struct ifaddrs* ifaddr = nullptr;
    if (getifaddrs(&ifaddr) != 0) {
        return "";
    }

    std::string mac;
    for (struct ifaddrs* ifa = ifaddr; ifa != nullptr; ifa = ifa->ifa_next) {
        if (!ifa->ifa_addr || ifa->ifa_addr->sa_family != AF_PACKET) {
            continue;
        }

        if ((ifa->ifa_flags & IFF_UP) == 0 || (ifa->ifa_flags & IFF_LOOPBACK) != 0) {
            continue;
        }

        const auto* s = reinterpret_cast<const struct sockaddr_ll*>(ifa->ifa_addr);
        if (s->sll_halen < 6) {
            continue;
        }

        char buf[32] = {0};
        std::snprintf(buf, sizeof(buf), "%02x:%02x:%02x:%02x:%02x:%02x",
            static_cast<unsigned char>(s->sll_addr[0]),
            static_cast<unsigned char>(s->sll_addr[1]),
            static_cast<unsigned char>(s->sll_addr[2]),
            static_cast<unsigned char>(s->sll_addr[3]),
            static_cast<unsigned char>(s->sll_addr[4]),
            static_cast<unsigned char>(s->sll_addr[5]));
        mac = buf;
        break;
    }

    freeifaddrs(ifaddr);
    return mac;
#else
    return "";
#endif
}

} // namespace

LicenseGuard::LicenseGuard(int fallback_max_connections)
    : fallback_max_connections_(fallback_max_connections) {
    // 启动时仅执行一次初始化与缓存，避免阻塞 Boost.Asio 的热路径
    InitializeCache();
}

void LicenseGuard::InitializeCache() {
    const bool required = GetEnvBool(kEnvLicenseRequired, true);
    const std::string token = GetEnvStr(kEnvLicenseToken);

    if (token.empty()) {
        if (!required) {
            is_valid_cache_ = true;
            max_devices_cache_ = fallback_max_connections_;
            exp_cache_ = std::numeric_limits<std::int64_t>::max(); // 永不过期
            cached_reason_ = "license_optional";
            cached_mac_ = "none";
            return;
        }
        is_valid_cache_ = false;
        cached_reason_ = "license_missing";
        return;
    }

    const std::size_t dot = token.find('.');
    if (dot == std::string::npos || dot == 0 || dot + 1 >= token.size()) {
        is_valid_cache_ = false;
        cached_reason_ = "license_format_invalid";
        return;
    }

    const std::string payload_b64 = token.substr(0, dot);
    const std::string sig_b64 = token.substr(dot + 1);

    const auto payload_raw = Base64UrlDecode(payload_b64);
    const auto sig = Base64UrlDecode(sig_b64);
    if (payload_raw.empty() || sig.empty()) {
        is_valid_cache_ = false;
        cached_reason_ = "license_base64_invalid";
        return;
    }

    const std::string payload(payload_raw.begin(), payload_raw.end());

    std::string pubkey = GetEnvStr(kEnvPublicKeyPem);
    if (pubkey.empty()) {
        pubkey = kVendorPublicKeyPem;
    }
    if (pubkey.find("REPLACE_WITH_VENDOR_PUBLIC_KEY") != std::string::npos) {
        is_valid_cache_ = false;
        cached_reason_ = "public_key_not_configured";
        return;
    }

    if (!VerifySignatureRsaPssSha256(payload, sig, pubkey)) {
        is_valid_cache_ = false;
        cached_reason_ = "license_signature_invalid";
        return;
    }

    json j;
    try {
        j = json::parse(payload);
    } catch (const std::exception&) {
        is_valid_cache_ = false;
        cached_reason_ = "license_payload_invalid";
        return;
    }

    if (!j.contains("exp") || !j.contains("max_devices") || !j.contains("mac")) {
        is_valid_cache_ = false;
        cached_reason_ = "license_fields_missing";
        return;
    }

    exp_cache_ = j["exp"].get<std::int64_t>();
    max_devices_cache_ = j["max_devices"].get<int>();
    cached_mac_ = NormalizeMac(j["mac"].get<std::string>());

    if (max_devices_cache_ <= 0) {
        is_valid_cache_ = false;
        cached_reason_ = "license_max_devices_invalid";
        return;
    }

    const std::string machine_mac = NormalizeMac(GetPrimaryMacAddress());
    if (machine_mac.empty()) {
        is_valid_cache_ = false;
        cached_reason_ = "machine_mac_unavailable";
        return;
    }
    if (machine_mac != cached_mac_) {
        Utils::Logger::Instance().Log(
            "ERROR",
            "MAC mismatch: machine_mac=" + machine_mac + ", license_mac=" + cached_mac_,
            "LicenseGuard");
        is_valid_cache_ = false;
        cached_reason_ = "license_mac_mismatch";
        return;
    }

    // 所有校验通过，标记缓存为有效
    is_valid_cache_ = true;
    cached_reason_ = "ok";
}

// 极速判断路径：完全没有耗时的 I/O 和加密计算
LicenseDecision LicenseGuard::Evaluate(std::size_t current_connections) const {
    LicenseDecision d;
    d.max_devices = max_devices_cache_ > 0 ? max_devices_cache_ : fallback_max_connections_;
    d.exp = exp_cache_;
    d.mac = cached_mac_;

    // 1. 如果初始化时的硬核校验失败，直接拦截
    if (!is_valid_cache_) {
        d.state = LicenseState::Invalid;
        d.reason = cached_reason_;
        return d;
    }

    // 2. 仅判断时间戳是否过期
    const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    if (static_cast<std::int64_t>(now) >= exp_cache_) {
        d.state = LicenseState::Expired;
        d.reason = "license_expired";
        return d;
    }

    // 3. 仅比对当前连接数是否超限
    if (current_connections >= static_cast<std::size_t>(d.max_devices)) {
        d.state = LicenseState::OverLimit;
        d.reason = "over_limit";
        return d;
    }

    d.state = LicenseState::Ok;
    d.reason = cached_reason_;
    return d;
}
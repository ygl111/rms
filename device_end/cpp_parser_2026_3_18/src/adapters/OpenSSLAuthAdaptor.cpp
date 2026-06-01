#include "dpower/utils/Auth.h" 

#include <openssl/hmac.h>
#include <openssl/sha.h>
#include <stdexcept>
#include <vector>

namespace DPower {
namespace Utils {

namespace { // 使用匿名命名空间来隐藏内部实现细节

// --- 内部辅助函数：独立的Base64编码实现 ---
// 为了不依赖您项目中的其他文件，这里提供一个自包含的实现
std::string base64_encode(const unsigned char* data, size_t input_length) {
    const char* base64_chars = 
                 "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                 "abcdefghijklmnopqrstuvwxyz"
                 "0123456789+/";
    
    std::string ret;
    int i = 0;
    int j = 0;
    unsigned char char_array_3[3];
    unsigned char char_array_4[4];

    while (input_length--) {
        char_array_3[i++] = *(data++);
        if (i == 3) {
            char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
            char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
            char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
            char_array_4[3] = char_array_3[2] & 0x3f;

            for(i = 0; (i <4) ; i++)
                ret += base64_chars[char_array_4[i]];
            i = 0;
        }
    }

    if (i) {
        for(j = i; j < 3; j++)
            char_array_3[j] = '\0';

        char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
        char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
        char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
        char_array_4[3] = char_array_3[2] & 0x3f;

        for (j = 0; (j < i + 1); j++)
            ret += base64_chars[char_array_4[j]];

        while((i++ < 3))
            ret += '=';
    }
    return ret;
}


// --- 鉴权码生成器的具体实现 ---
class OpenSSLAuthGenerator : public DPowerAuthGenerator {
public:
    std::string Generate(const std::string& data, const std::string& key) const override {
        unsigned char hmac_result[EVP_MAX_MD_SIZE];
        unsigned int hmac_len = 0;

        // 使用OpenSSL计算HMAC-SHA256
        HMAC(EVP_sha256(),
             key.c_str(),
             key.length(),
             reinterpret_cast<const unsigned char*>(data.c_str()),
             data.length(),
             hmac_result,
             &hmac_len);

        if (hmac_len == 0) {
            throw std::runtime_error("HMAC-SHA256 calculation failed.");
        }

        // 使用内部的Base64函数进行编码
        return base64_encode(hmac_result, hmac_len);
    }
};

// --- 工厂的具体实现 ---
class OpenSSLAuthFactory : public DPowerAuthFactory {
public:
    AuthGeneratorPtr Create() override {
        return std::make_unique<OpenSSLAuthGenerator>();
    }
};

} // 匿名命名空间结束

// --- 对外可见的工厂创建函数实现 ---
AuthFactoryPtr CreateOpenSSLAuthFactory() {
    return std::make_unique<OpenSSLAuthFactory>();
}

} // namespace Utils
} // namespace DPower

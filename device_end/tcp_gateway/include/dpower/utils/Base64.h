#pragma once
// ================================================================
//  DPower::Utils::Base64 抽象接口
// ================================================================

#include <string>
#include <vector>

namespace DPower {
namespace Utils {

class DPowerBase64 {
public:
    // 计算编码后的大小
    static std::size_t EncodedSize(std::size_t input_size);

    // 计算解码后的大小
    static std::size_t DecodedSize(std::size_t input_size);

    // 编码：将二进制数据编码为 Base64 字符串
    static std::string Encode(const void* data, std::size_t size);

    // 解码：将 Base64字符串解码为二进制数据
    // 返回解码后的数据大小
    static std::pair<std::size_t, std::size_t> Decode(void* output, const char* input, std::size_t input_size);
};

} // namespace Utils
} // namespace DPower 

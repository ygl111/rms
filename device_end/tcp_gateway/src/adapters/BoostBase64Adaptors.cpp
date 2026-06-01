#include "dpower/utils/Base64.h" // 假设头文件路径正确
#include <boost/beast/core/detail/base64.hpp>
#include <string>
#include <vector>

namespace DPower {
namespace Utils {

// 使用 :: 代替 :
std::size_t DPowerBase64::EncodedSize(std::size_t input_size) {
    return boost::beast::detail::base64::encoded_size(input_size);
}

// 使用 :: 代替 :
std::size_t DPowerBase64::DecodedSize(std::size_t input_size) {
    return boost::beast::detail::base64::decoded_size(input_size);
}

std::string DPowerBase64::Encode(const void* data, std::size_t size) {
    const auto encoded_size = boost::beast::detail::base64::encoded_size(size);
    // 修正了无效的初始化和语法错误
    std::string result(encoded_size, '\0');
    boost::beast::detail::base64::encode(&result[0], data, size);
    return result;
}

std::pair<std::size_t, std::size_t> DPowerBase64::Decode(void* output, const char* input, std::size_t input_size) {
    // 修正了函数名拼写错误 base64code -> base64::decode
    auto result = boost::beast::detail::base64::decode(output, input, input_size);
    return {result.first, result.second};
}

} // namespace Utils
} // namespace DPower

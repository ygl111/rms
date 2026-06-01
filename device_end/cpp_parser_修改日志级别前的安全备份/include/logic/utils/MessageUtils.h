#pragma once

#include <string>
#include <vector>
#include <iomanip>
#include <sstream>
#include <algorithm>
#include <json.hpp>
#include "logic/UniversalParser.h"  // 包含ParsedMessage定义

/**
 * @brief 消息处理工具类
 * 提供通用的消息处理工具函数
 */
class MessageUtils {
public:
    /**
     * @brief 将字节向量转换为可读字符串
     * @param v 字节向量
     * @return 可读字符串
     */
    static std::string VecToReadable(const std::vector<uint8_t>& v);
    
    /**
     * @brief 将解析后的消息转换为JSON格式（用于调试）
     * @param parsed_msg 解析后的消息
     * @return JSON字符串
     */
    static std::string MessageToJson(const UniversalParsedMessage& parsed_msg);
    
    /**
     * @brief 将字节向量转换为十六进制字符串
     * @param v 字节向量
     * @return 十六进制字符串
     */
    static std::string VecToHexString(const std::vector<uint8_t>& v);
    
    /**
     * @brief 将十六进制字符串转换为字节向量
     * @param hex_str 十六进制字符串
     * @return 字节向量
     */
    static std::vector<uint8_t> HexStringToVec(const std::string& hex_str);
    
    /**
     * @brief 清理字符串数据，检测填充值并转换为空字符串
     * @param data 原始字节数据
     * @return 清理后的字符串
     */
    static std::string CleanString(const std::vector<uint8_t>& data);
    
    /**
     * @brief 清理字符串数据，移除填充字符和无效字符
     * @param str 原始字符串
     * @return 清理后的字符串
     */
    static std::string CleanString(const std::string& str);

    /**
     * @brief 校验字符串是否为有效 UTF-8。
     */
    static bool IsValidUtf8(const std::string& s);

    /**
     * @brief 规范化字符串为适合数据库入库的格式。
     * 优先保持原样（若已是 UTF-8），否则按 CP1252/Latin-1 映射转为 UTF-8；
     * 同时会去除尾随空字节/空格与常见填充。
     */
    static std::string NormalizeForDb(const std::string& s);

    /**
     * @brief 字节数据版本的规范化（先 Clean 再 NormalizeForDb）。
     */
    static std::string NormalizeForDb(const std::vector<uint8_t>& data);
}; 
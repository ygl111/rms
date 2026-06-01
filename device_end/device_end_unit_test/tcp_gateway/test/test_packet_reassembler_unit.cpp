/**
 * @file test_packet_reassembler_unit.cpp  
 * @brief 分包重组器单元测试 - 第四优先级测试
 * @author AI Assistant
 * @date 2025-09-26
 * 
 * 测试重点：分包重组逻辑、缓冲区管理、超时处理、内存管理
 */

#include <gtest/gtest.h>
#include <gmock/gmock.h>
#include <memory>
#include <vector>
#include <chrono>

// 包含待测试的头文件
#include "logic/PacketReassembler.h"

class PacketReassemblerTest : public ::testing::Test {
protected:
    void SetUp() override {
        reassembler_ = std::make_unique<PacketReassembler>();
    }

    void TearDown() override {
        // 清理资源
    }

    // 创建测试用的分包数据
    std::vector<std::vector<uint8_t>> CreateTestFragments() {
        // 模拟一个被分成3个包的消息
        std::vector<std::vector<uint8_t>> fragments;
        
        // 第一个分包 (包含头部)
        fragments.push_back({
            0x55, 0x55,           // 协议头
            0x03,                 // 消息类型
            0x00, 0x20,           // 总长度 32字节
            0x01,                 // 包序号
            0xE9, 0x03,           // 消息ID
            0x01, 0x02, 0x03, 0x04 // 部分数据
        });
        
        // 第二个分包
        fragments.push_back({
            0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0x0C
        });
        
        // 第三个分包 (结束)
        fragments.push_back({
            0x0D, 0x0E, 0x0F, 0x10,
            0x11, 0x12, 0x13, 0x14
        });
        
        return fragments;
    }

    std::unique_ptr<PacketReassembler> reassembler_;
};

// 🔥 核心测试：完整数据包处理
TEST_F(PacketReassemblerTest, CompletePacketProcessing) {
    // 测试完整的、不需要重组的数据包
    std::vector<uint8_t> complete_packet = {
        0x55, 0x55, 0x03, 0x00, 0x10, 0x00,
        0xE9, 0x03, 'T', 'E', 'S', 'T',
        0x01, 0x02, 0x03, 0x04
    };
    
    std::string session_id = "test_session_001";
    
    auto result = reassembler_->ProcessPacket(session_id, complete_packet);
    
    // 完整包应该立即返回结果
    EXPECT_TRUE(result.is_complete);
    EXPECT_FALSE(result.reassembled_data.empty());
    EXPECT_EQ(result.reassembled_data.size(), complete_packet.size());
    EXPECT_EQ(result.reassembled_data, complete_packet);
}

// 🔥 核心测试：分包重组逻辑
TEST_F(PacketReassemblerTest, FragmentReassemblyLogic) {
    auto fragments = CreateTestFragments();
    std::string session_id = "test_session_002";
    
    // 处理第一个分包
    auto result1 = reassembler_->ProcessPacket(session_id, fragments[0]);
    EXPECT_FALSE(result1.is_complete);  // 第一包不完整
    EXPECT_TRUE(result1.reassembled_data.empty());
    
    // 处理第二个分包
    auto result2 = reassembler_->ProcessPacket(session_id, fragments[1]);
    EXPECT_FALSE(result2.is_complete);  // 还不完整
    EXPECT_TRUE(result2.reassembled_data.empty());
    
    // 处理第三个分包（最后一包）
    auto result3 = reassembler_->ProcessPacket(session_id, fragments[2]);
    EXPECT_TRUE(result3.is_complete);   // 现在完整了
    EXPECT_FALSE(result3.reassembled_data.empty());
    
    // 验证重组后的数据完整性
    size_t expected_total_size = fragments[0].size() + fragments[1].size() + fragments[2].size();
    EXPECT_EQ(result3.reassembled_data.size(), expected_total_size);
}

// 🔥 核心测试：乱序分包处理
TEST_F(PacketReassemblerTest, OutOfOrderFragmentHandling) {
    auto fragments = CreateTestFragments();
    std::string session_id = "test_session_003";
    
    // 先发送第三个分包
    auto result1 = reassembler_->ProcessPacket(session_id, fragments[2]);
    EXPECT_FALSE(result1.is_complete);
    
    // 再发送第一个分包
    auto result2 = reassembler_->ProcessPacket(session_id, fragments[0]);
    EXPECT_FALSE(result2.is_complete);
    
    // 最后发送第二个分包
    auto result3 = reassembler_->ProcessPacket(session_id, fragments[1]);
    EXPECT_TRUE(result3.is_complete);
    
    // 验证重组结果正确
    EXPECT_FALSE(result3.reassembled_data.empty());
}

// 🔥 缓冲区管理测试：多会话并发处理
TEST_F(PacketReassemblerTest, MultiSessionConcurrentProcessing) {
    auto fragments = CreateTestFragments();
    
    // 同时处理两个不同会话的分包
    std::string session1 = "session_001";
    std::string session2 = "session_002";
    
    // 会话1：发送第一个分包
    auto result1_1 = reassembler_->ProcessPacket(session1, fragments[0]);
    EXPECT_FALSE(result1_1.is_complete);
    
    // 会话2：发送第一个分包
    auto result2_1 = reassembler_->ProcessPacket(session2, fragments[0]);
    EXPECT_FALSE(result2_1.is_complete);
    
    // 会话1：完成重组
    reassembler_->ProcessPacket(session1, fragments[1]);
    auto result1_3 = reassembler_->ProcessPacket(session1, fragments[2]);
    EXPECT_TRUE(result1_3.is_complete);
    
    // 会话2：也完成重组
    reassembler_->ProcessPacket(session2, fragments[1]);
    auto result2_3 = reassembler_->ProcessPacket(session2, fragments[2]);
    EXPECT_TRUE(result2_3.is_complete);
}

// 🔥 超时处理测试：超时清理机制
TEST_F(PacketReassemblerTest, TimeoutCleanupMechanism) {
    // 这个测试需要根据实际的超时实现来调整
    auto fragments = CreateTestFragments();
    std::string session_id = "test_session_timeout";
    
    // 发送第一个分包
    reassembler_->ProcessPacket(session_id, fragments[0]);
    
    // 模拟超时（这里需要根据实际实现调整）
    // reassembler_->TriggerTimeoutCleanup();
    
    // 验证超时后的状态清理
    // EXPECT_FALSE(reassembler_->HasPendingFragments(session_id));
    
    // 临时跳过，需要实际的超时实现
    GTEST_SKIP() << "需要实际的超时机制实现";
}

// 🔥 内存管理测试：大量分包处理
TEST_F(PacketReassemblerTest, MemoryManagementUnderLoad) {
    // 创建大量会话和分包，测试内存使用
    const int session_count = 100;
    auto fragments = CreateTestFragments();
    
    for (int i = 0; i < session_count; ++i) {
        std::string session_id = "session_" + std::to_string(i);
        
        // 只发送第一个分包，让它们在缓冲区中等待
        auto result = reassembler_->ProcessPacket(session_id, fragments[0]);
        EXPECT_FALSE(result.is_complete);
    }
    
    // 这里可以检查内存使用情况（如果有相应的接口）
    // EXPECT_LT(reassembler_->GetMemoryUsage(), MAX_EXPECTED_MEMORY);
    
    // 清理所有待处理的分包
    reassembler_->ClearAllPendingFragments();
}

// 🔥 错误处理测试：无效分包处理
TEST_F(PacketReassemblerTest, InvalidFragmentHandling) {
    std::string session_id = "test_session_invalid";
    
    // 测试空数据包
    std::vector<uint8_t> empty_packet;
    auto result1 = reassembler_->ProcessPacket(session_id, empty_packet);
    EXPECT_FALSE(result1.is_complete);
    EXPECT_TRUE(result1.error_message.find("empty") != std::string::npos);
    
    // 测试过短的数据包
    std::vector<uint8_t> too_short = {0x55};
    auto result2 = reassembler_->ProcessPacket(session_id, too_short);
    EXPECT_FALSE(result2.is_complete);
    EXPECT_TRUE(result2.error_message.find("too short") != std::string::npos);
    
    // 测试无效的协议头
    std::vector<uint8_t> invalid_header = {0xFF, 0xFF, 0x00, 0x00, 0x10, 0x00};
    auto result3 = reassembler_->ProcessPacket(session_id, invalid_header);
    EXPECT_FALSE(result3.is_complete);
    EXPECT_TRUE(result3.error_message.find("invalid header") != std::string::npos);
}

// 主函数
int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
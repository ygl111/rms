#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能测试脚本 - 专门用于5000台设备并发测试
优化后的版本，专注于实现100%响应率
"""

import argparse
import time
import sys
import os
import logging
from enhanced_device_simulator import DeviceSimulatorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('HighPerformanceTest')


def run_high_performance_test(device_count: int = 5000, 
                             test_duration: int = 60,
                             environment: str = "local"):
    """运行高性能测试"""
    
    print(f"🚀 开始高性能测试 - {device_count} 台设备")
    print(f"📊 优化配置:")
    print(f"   - 最大并发连接: 500")
    print(f"   - 连接超时: 5秒")
    print(f"   - 读写超时: 8秒") 
    print(f"   - 消息重试: 3次")
    print(f"   - 发送超时: 4秒")
    print(f"   - 连接池大小: 500")
    print(f"   - 发送并发度: 200")
    print("")
    
    # 创建管理器
    manager = DeviceSimulatorManager("test_config.json", environment)
    manager.global_test_start_time = time.time()
    manager.configured_test_duration = test_duration
    
    try:
        # 1. 检查测试设备
        print("📋 检查测试设备...")
        devices = manager.load_test_devices("PERF_TEST", device_count)
        
        if len(devices) < device_count:
            print(f"⚠️  警告: 只找到 {len(devices)} 台测试设备，少于请求的 {device_count} 台")
            print(f"   请运行以下命令创建足够的测试设备:")
            print(f"   python device_batch_inserter.py --count {device_count} --prefix PERF_TEST")
            
            # 如果设备数少于1000台，直接退出
            if len(devices) < 1000:
                print("❌ 测试设备数量不足，退出测试")
                return False
            
            device_count = len(devices)
            print(f"✅ 使用现有的 {device_count} 台测试设备继续测试")
        else:
            print(f"✅ 找到 {device_count} 台测试设备")
        
        # 2. 创建设备仿真器
        print("🔧 创建设备仿真器...")
        manager.create_simulators(devices)
        print(f"✅ 创建了 {len(manager.simulators)} 个设备仿真器")
        
        # 3. 高性能并发连接测试
        print(f"⚡ 开始高性能并发连接 ({device_count} 台设备)...")
        
        connection_start = time.time()
        results = manager.start_all_simulators(
            registration_interval=0.001,  # 极小的间隔
            max_concurrent=500  # 高并发度
        )
        connection_time = time.time() - connection_start
        
        # 计算成功率
        success_rate = (results['authenticated'] / results['total']) * 100 if results['total'] > 0 else 0
        throughput = results['authenticated'] / connection_time if connection_time > 0 else 0
        
        print(f"\n📊 连接测试结果:")
        print(f"   总设备数: {results['total']}")
        print(f"   连接成功: {results['connected']}")
        print(f"   注册成功: {results['registered']}")
        print(f"   鉴权成功: {results['authenticated']}")
        print(f"   失败数量: {results['failed']}")
        print(f"   成功率: {success_rate:.2f}%")
        print(f"   总耗时: {connection_time:.2f}秒")
        print(f"   吞吐量: {throughput:.1f} 设备/秒")
        
        if success_rate < 95.0:
            print(f"⚠️  警告: 成功率 {success_rate:.2f}% 低于目标值 95%")
        else:
            print(f"✅ 成功率 {success_rate:.2f}% 达到目标")
        
        # 4. 消息发送测试
        if results['authenticated'] > 0:
            print(f"\n📨 开始消息发送测试...")
            
            # 发送少量测试消息以验证响应能力
            manager.send_test_messages(
                message_count=2,  # 每设备2条消息
                interval=0.2,  # 200ms间隔
                send_concurrency=200,  # 高并发发送
                recv_timeout=4.0,  # 4秒接收超时
                max_retries=3,  # 3次重试
                max_notes=200  # 限制点钞张数
            )
            
            # 启动心跳
            manager.start_heartbeat_for_all(30)
            
            # 等待测试时间
            print(f"⏰ 等待测试运行 {test_duration} 秒...")
            time.sleep(test_duration)
            
            # 统计最终结果
            print("\n📊 最终统计结果:")
            stats_list = manager.get_all_stats()
            
            total_messages_sent = sum(s['messages_sent'] for s in stats_list)
            total_messages_received = sum(s['messages_received'] for s in stats_list)
            total_fault_sent = sum(s.get('fault_reports_sent', 0) for s in stats_list)
            total_fault_received = sum(s.get('fault_reports_received', 0) for s in stats_list)
            total_banknote_sent = sum(s.get('banknote_reports_sent', 0) for s in stats_list)
            total_banknote_received = sum(s.get('banknote_reports_received', 0) for s in stats_list)
            
            # 计算响应率
            message_response_rate = (total_messages_received / total_messages_sent * 100) if total_messages_sent > 0 else 0
            fault_response_rate = (total_fault_received / total_fault_sent * 100) if total_fault_sent > 0 else 0
            banknote_response_rate = (total_banknote_received / total_banknote_sent * 100) if total_banknote_sent > 0 else 0
            
            print(f"   连接设备数: {sum(1 for s in stats_list if s['connected'])}")
            print(f"   总发送消息: {total_messages_sent}")
            print(f"   总接收响应: {total_messages_received}")
            print(f"   整体响应率: {message_response_rate:.2f}%")
            print(f"   故障上报响应率: {fault_response_rate:.2f}%")
            print(f"   点钞上报响应率: {banknote_response_rate:.2f}%")
            
            # 判断测试是否成功
            target_response_rate = 100.0
            if message_response_rate >= target_response_rate:
                print(f"🎉 测试成功! 响应率 {message_response_rate:.2f}% 达到目标 {target_response_rate}%")
                test_success = True
            else:
                print(f"❌ 测试未完全达标: 响应率 {message_response_rate:.2f}% 低于目标 {target_response_rate}%")
                test_success = False
            
            # 生成报告
            manager.global_test_end_time = time.time()
            manager.global_test_duration = manager.global_test_end_time - manager.global_test_start_time
            
            print(f"\n📄 生成测试报告...")
            report_file = manager.generate_simple_report()
            if report_file:
                print(f"✅ 报告已生成: {report_file}")
            
            return test_success
        else:
            print("❌ 无设备成功认证，测试失败")
            return False
            
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return False
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        logger.exception("测试异常")
        return False
    finally:
        if manager.global_test_start_time and not manager.global_test_end_time:
            manager.global_test_end_time = time.time()
            manager.global_test_duration = manager.global_test_end_time - manager.global_test_start_time
        
        manager.stop_all_simulators()
        total_time = manager.global_test_duration
        if total_time:
            print(f"⏱️  总测试时长: {total_time:.2f} 秒")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="高性能设备测试")
    parser.add_argument("--device-count", type=int, default=5000, 
                       help="要测试的设备数量 (默认: 5000)")
    parser.add_argument("--test-duration", type=int, default=60, 
                       help="测试持续时间(秒) (默认: 60)")
    parser.add_argument("--environment", type=str, default="local", 
                       choices=["local", "vm", "staging"],
                       help="测试环境 (默认: local)")
    
    args = parser.parse_args()
    
    print("🚀 高性能设备仿真测试")
    print("=" * 60)
    print(f"设备数量: {args.device_count}")
    print(f"测试时长: {args.test_duration}秒")
    print(f"测试环境: {args.environment}")
    print("=" * 60)
    
    success = run_high_performance_test(
        device_count=args.device_count,
        test_duration=args.test_duration,
        environment=args.environment
    )
    
    if success:
        print("\n🎉 高性能测试完成!")
        sys.exit(0)
    else:
        print("\n❌ 高性能测试未完全达标")
        sys.exit(1)


if __name__ == "__main__":
    main()
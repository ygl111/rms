#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速内存占用测试脚本
用于快速验证内存占用情况的简化版本
"""

import time
import threading
import random
import logging
import gc
import sys
import os
import argparse
import concurrent.futures
from threading import Lock
from datetime import datetime
from enhanced_device_simulator import EnhancedDeviceSimulator, DeviceSimulatorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('QuickMemoryTest')


def get_memory_usage():
    """获取当前内存使用情况"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # 物理内存使用量
            'vms_mb': memory_info.vms / 1024 / 1024   # 虚拟内存使用量
        }
    except ImportError:
        # 备用方法1：使用resource模块
        try:
            import resource
            rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # 在Linux上ru_maxrss是KB，在macOS上是bytes
            if sys.platform == 'darwin':  # macOS
                rss_mb = rss_kb / 1024 / 1024
            else:  # Linux
                rss_mb = rss_kb / 1024
            return {'rss_mb': rss_mb, 'vms_mb': 0.0}
        except:
            # 备用方法2：通过/proc/meminfo（仅Linux）
            try:
                with open('/proc/self/status', 'r') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            rss_kb = int(line.split()[1])
                            return {'rss_mb': rss_kb / 1024, 'vms_mb': 0.0}
            except:
                return {'rss_mb': 0.0, 'vms_mb': 0.0}


def run_single_device_memory_test(test_minutes=30, unused_param=0):
    """单台设备内存测试 - 持续发送模式"""
    logger.info("🚀 启动单台设备持续发送内存测试")
    logger.info("=" * 70)
    logger.info("💰 单台设备连续点钞内存占用测试")
    logger.info("🎯 测试参数:")
    logger.info(f"   设备数量: 1 台")
    logger.info(f"   持续时长: {test_minutes} 分钟")
    logger.info("   发送模式: 持续不断发送")
    logger.info("   每条报告钞票数: 200 张")
    logger.info("=" * 70)
    
    try:
        # 记录初始内存
        initial_memory = get_memory_usage()
        logger.info(f"📊 初始内存: RSS={initial_memory['rss_mb']:.1f}MB")
        
        # 创建设备管理器
        manager = DeviceSimulatorManager("test_config.json")
        
        # 加载1台测试设备
        logger.info("🔧 正在加载1台测试设备...")
        device_configs = manager.load_test_devices("PERF_100K", 1)
        
        if len(device_configs) == 0:
            logger.error("❌ 未找到测试设备")
            return
            
        logger.info("✅ 成功加载1台测试设备")
        
        # 创建设备模拟器
        manager.create_simulators(device_configs)
        after_create_memory = get_memory_usage()
        create_growth = after_create_memory['rss_mb'] - initial_memory['rss_mb']
        logger.info(f"📊 创建设备后内存: RSS={after_create_memory['rss_mb']:.1f}MB (增长{create_growth:.1f}MB)")
        
        # 连接设备
        logger.info("📡 连接设备...")
        result = manager.start_all_simulators(registration_interval=0.01, max_concurrent=1)
        connected_count = result.get('connected', 0)
        
        if connected_count == 0:
            logger.error("❌ 设备连接失败")
            return
            
        logger.info("✅ 设备连接成功")
        
        # 连接后基线内存
        baseline_memory = get_memory_usage()
        connect_growth = baseline_memory['rss_mb'] - after_create_memory['rss_mb']
        logger.info(f"📊 连接基线内存: RSS={baseline_memory['rss_mb']:.1f}MB (连接增长{connect_growth:.1f}MB)")
        
        # 获取连接的设备
        device = None
        for sim in manager.simulators:
            if hasattr(sim, 'connected') and sim.connected:
                device = sim
                break
                
        if not device:
            logger.error("❌ 没有找到已连接的设备")
            return
        
        # 开始持续发送点钞报告
        logger.info(f"🚀 开始持续发送点钞报告 {test_minutes} 分钟...")
        logger.info("💰 每条报告包含200张钞票，持续不断发送")
        
        test_start_time = time.time()
        test_duration = test_minutes * 60  # 测试持续时间（秒）
        
        sent_count = 0
        success_count = 0
        last_report_time = test_start_time
        
        # 持续发送直到时间结束
        while (time.time() - test_start_time) < test_duration:
            try:
                # 发送包含200张钞票的点钞报告
                success = device.send_banknote_report(
                    total_notes=200,  # 固定200张钞票
                    max_retries=1,
                    recv_timeout=1.0  # 短超时，快速发送
                )
                
                sent_count += 1
                if success:
                    success_count += 1
                
                # 每30秒报告一次进度
                current_time = time.time()
                if current_time - last_report_time >= 30:  # 30秒
                    elapsed_time = (current_time - test_start_time) / 60
                    remaining_time = test_minutes - elapsed_time
                    current_memory = get_memory_usage()
                    memory_growth = current_memory['rss_mb'] - baseline_memory['rss_mb']
                    per_report_memory = memory_growth / sent_count if sent_count > 0 else 0
                    
                    logger.info(f"📊 持续发送中 ({elapsed_time:.1f}/{test_minutes}分钟，剩余{remaining_time:.1f}分钟):")
                    logger.info(f"   已发送: {sent_count} 条报告")
                    logger.info(f"   当前内存: {current_memory['rss_mb']:.1f}MB")
                    logger.info(f"   内存增长: {memory_growth:.3f}MB ({memory_growth*1024:.1f}KB)")
                    logger.info(f"   每条报告: {per_report_memory*1024:.3f}KB")
                    logger.info(f"   成功率: {success_count/sent_count*100:.1f}%")
                    
                    last_report_time = current_time
                
                # 不加延迟，持续发送（最多加很短的间隔避免CPU过载）
                time.sleep(0.01)  # 10ms间隔，几乎连续发送
                    
            except Exception as e:
                sent_count += 1
                # 简化错误处理，继续发送
                time.sleep(0.05)  # 出错时稍作延迟
        
        # 测试完成，计算最终结果
        test_end_time = time.time()
        final_memory = get_memory_usage()
        actual_test_time = (test_end_time - test_start_time) / 60
        
        # 计算关键指标
        total_memory_growth = final_memory['rss_mb'] - baseline_memory['rss_mb']
        per_report_memory_kb = (total_memory_growth * 1024) / sent_count if sent_count > 0 else 0
        
        # 显示最终结果
        logger.info("=" * 70)
        logger.info("🎯 单台设备内存测试完成！")
        logger.info("=" * 70)
        
        logger.info(f"📊 测试统计:")
        logger.info(f"   实际测试时间: {actual_test_time:.1f} 分钟")
        logger.info(f"   发送报告总数: {sent_count} 条")
        logger.info(f"   成功发送数量: {success_count} 条")
        logger.info(f"   成功率: {success_count/sent_count*100:.1f}%")
        
        logger.info(f"📈 内存分析:")
        logger.info(f"   基线内存: {baseline_memory['rss_mb']:.1f}MB")
        logger.info(f"   最终内存: {final_memory['rss_mb']:.1f}MB")
        logger.info(f"   报文内存增长: {total_memory_growth:.3f}MB ({total_memory_growth*1024:.1f}KB)")
        
        logger.info("=" * 70)
        logger.info("🎯 测试结论")
        logger.info("=" * 70)
        logger.info(f"� 测试数据:")
        logger.info(f"   持续发送时间: {actual_test_time:.1f} 分钟")
        logger.info(f"   发送报文总数: {sent_count} 条")
        logger.info(f"   系统内存增长: {total_memory_growth*1024:.0f}KB")
        logger.info("")
        logger.info("🏆 最终结论:")
        logger.info(f"   系统处理单台设备持续发送200张钞票点钞报文的内存开销: {total_memory_growth*1024:.0f}KB")
        logger.info("=" * 70)
        
        # 清理
        manager.stop_all_simulators()
        
    except Exception as e:
        logger.error(f"测试异常: {e}")
        import traceback
        traceback.print_exc()


def run_quick_memory_test(device_count=100, test_minutes=10, reports_per_device=20, notes_per_report=200):
    """运行快速内存占用测试"""
    logger.info("🚀 启动快速内存占用测试")
    logger.info("=" * 70)
    logger.info("💰 快速内存占用测试")
    logger.info("🎯 测试参数:")
    logger.info(f"   设备数量: {device_count} 台")
    logger.info(f"   测试时长: {test_minutes} 分钟")
    logger.info(f"   每台设备点钞报告数: {reports_per_device} 条")
    logger.info(f"   每条报告钞票数: {notes_per_report} 张")
    logger.info(f"   预期总点钞报告: {device_count * reports_per_device} 条")
    logger.info(f"   预期总钞票处理数: {device_count * reports_per_device * notes_per_report} 张")
    logger.info("=" * 70)
    
    # 记录初始内存
    initial_memory = get_memory_usage()
    logger.info(f"📊 初始内存: RSS={initial_memory['rss_mb']:.1f}MB, VMS={initial_memory['vms_mb']:.1f}MB")
    
    try:
        # 创建设备管理器
        manager = DeviceSimulatorManager("test_config.json")
        
        # 生成测试设备
        logger.info(f"🔧 正在生成 {device_count} 台测试设备...")
        device_configs = manager.load_test_devices("PERF_100K", device_count)
        
        if len(device_configs) < device_count:
            logger.warning(f"只生成了 {len(device_configs)} 台设备")
            device_count = len(device_configs)
        
        # 创建设备模拟器
        manager.create_simulators(device_configs)
        after_create_memory = get_memory_usage()
        create_growth = after_create_memory['rss_mb'] - initial_memory['rss_mb']
        logger.info(f"📊 创建设备后内存: RSS={after_create_memory['rss_mb']:.1f}MB (增长{create_growth:.1f}MB)")
        
        # 连接设备 - 使用高效批量连接方法
        logger.info(f"📡 正在批量连接和认证设备...")
        connect_start_time = time.time()
        
        # 使用DeviceSimulatorManager的批量启动方法
        results = manager.start_all_simulators(
            registration_interval=0.001,  # 快速注册间隔
            max_concurrent=200  # 提高并发数
        )
        
        connect_time = time.time() - connect_start_time
        connected_count = results['authenticated']  # 使用认证成功的设备数
        failed_count = results['total'] - connected_count
        
        after_connect_memory = get_memory_usage()
        connect_growth = after_connect_memory['rss_mb'] - after_create_memory['rss_mb']
        connect_speed = device_count / connect_time if connect_time > 0 else 0
        
        logger.info(f"⚡ 批量连接完成 - 耗时 {connect_time:.2f}秒，速度 {connect_speed:.1f} 设备/秒")
        logger.info(f"✅ 连接完成: {connected_count}/{device_count} 台成功，{failed_count} 台失败")
        logger.info(f"📊 连接设备后内存: RSS={after_connect_memory['rss_mb']:.1f}MB (增长{connect_growth:.1f}MB)")
        
        # 显示详细的连接统计
        if 'errors' in results and results['errors']:
            logger.warning(f"⚠️ 连接错误前5条: {results['errors'][:5]}")
        
        logger.info(f"📈 详细统计: 连接 {results['connected']}, 注册 {results['registered']}, 认证 {results['authenticated']}")
        
        # 连接成功率检查
        connection_rate = connected_count / device_count if device_count > 0 else 0
        if connected_count == 0:
            logger.error("❌ 没有设备成功连接，测试终止")
            logger.error("🔧 可能原因:")
            logger.error("   1. TCP Gateway服务未启动或端口不正确")
            logger.error("   2. 数据库连接问题")
            logger.error("   3. 设备认证配置错误")
            logger.error("   4. 网络连接问题")
            return
        elif connection_rate < 0.5:
            logger.warning(f"⚠️ 连接成功率较低: {connection_rate:.1%}")
            logger.warning("建议检查网络和服务器配置")
        
        # 开始发送点钞报告 - 使用并发发送
        logger.info(f"💰 开始并发发送点钞报告...")
        logger.info(f"📋 {connected_count}台设备将并发发送，每台发送{reports_per_device}条点钞报告")
        logger.info(f"💰 每条点钞报告包含{notes_per_report}张钞票数据")
        
        test_duration = test_minutes * 60  # 转换为秒
        
        # 统计变量和锁
        total_sent = 0
        total_success = 0
        stats_lock = Lock()
        
        def device_sending_worker(sim):
            """每个设备的发送工作线程"""
            device_sent = 0
            device_success = 0
            device_start_time = time.time()
            
            # 计算每台设备的发送间隔（在测试时间内均匀分布）
            # 计算每条报告的发送间隔
            device_interval = test_duration / reports_per_device if reports_per_device > 0 else 1.0
            
            for i in range(reports_per_device):
                # 检查是否还在测试时间内
                if time.time() - device_start_time >= test_duration:
                    break
                    
                try:
                    success = sim.send_banknote_report(
                        total_notes=notes_per_report,  # 使用固定的钞票数量
                        max_retries=1,  # 减少重试次数提高速度
                        recv_timeout=2.0  # 减少超时时间
                    )
                    
                    device_sent += 1
                    if success:
                        device_success += 1
                        
                    # 更新全局统计
                    with stats_lock:
                        nonlocal total_sent, total_success
                        total_sent += 1
                        if success:
                            total_success += 1
                            
                    # 发送间隔控制（最小0.1秒间隔避免过快）
                    if i < reports_per_device - 1:  # 最后一条不用等待
                        actual_interval = max(0.1, device_interval + random.uniform(-device_interval*0.1, device_interval*0.1))
                        time.sleep(actual_interval)
                        
                except Exception as e:
                    device_sent += 1
                    with stats_lock:
                        total_sent += 1
                    # 简化错误处理，不打印大量错误日志
            
            return device_sent, device_success
        
        start_time = time.time()
        last_report_time = start_time
        
        # 启动并发发送
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(connected_count, 200)) as executor:
            # 提交所有设备的发送任务
            future_to_sim = {
                executor.submit(device_sending_worker, sim): sim 
                for sim in manager.simulators if hasattr(sim, 'connected') and sim.connected
            }
            
            logger.info(f"🚀 已启动 {len(future_to_sim)} 个并发发送线程")
            
            # 监控发送进度
            while True:
                current_time = time.time()
                elapsed_minutes = (current_time - start_time) / 60
                
                # 每2分钟报告一次进度
                if current_time - last_report_time >= 120:  # 2分钟
                    with stats_lock:
                        current_sent = total_sent
                        current_success = total_success
                    
                    success_rate = (current_success / current_sent * 100) if current_sent > 0 else 0
                    expected_total = connected_count * reports_per_device
                    progress_rate = (current_sent / expected_total * 100) if expected_total > 0 else 0
                    
                    current_memory = get_memory_usage()
                    memory_growth = current_memory['rss_mb'] - initial_memory['rss_mb']
                    
                    logger.info(f"📊 进度报告 ({elapsed_minutes:.1f}分钟):")
                    logger.info(f"   发送进度: {progress_rate:.1f}% ({current_sent}/{expected_total})")
                    logger.info(f"   成功率: {success_rate:.1f}% ({current_success}/{current_sent})")
                    logger.info(f"   当前内存: {current_memory['rss_mb']:.1f}MB (增长{memory_growth:.1f}MB)")
                    
                    last_report_time = current_time
                
                # 检查是否所有线程完成或测试时间结束
                if elapsed_minutes >= test_minutes:
                    logger.info("⏰ 测试时间结束，正在停止发送...")
                    break
                
                # 检查是否所有任务完成
                completed_count = sum(1 for f in future_to_sim if f.done())
                if completed_count == len(future_to_sim):
                    logger.info("✅ 所有发送任务完成")
                    break
                
                time.sleep(5)  # 每5秒检查一次
            
            # 等待所有任务完成并收集结果
            logger.info("📋 正在收集发送结果...")
            device_results = []
            for future in concurrent.futures.as_completed(future_to_sim, timeout=30):
                try:
                    device_sent, device_success = future.result()
                    device_results.append((device_sent, device_success))
                except Exception as e:
                    logger.warning(f"设备发送任务异常: {e}")
        
        # 最终测试结果统计
        end_time = time.time()
        final_memory = get_memory_usage()
        total_memory_growth = final_memory['rss_mb'] - initial_memory['rss_mb']
        actual_test_time = (end_time - start_time) / 60
        
        logger.info("=" * 70)
        logger.info("📈 测试完成 - 最终统计结果")
        logger.info("=" * 70)
        
        with stats_lock:
            final_sent = total_sent
            final_success = total_success
        
        final_success_rate = (final_success / final_sent * 100) if final_sent > 0 else 0
        expected_total = connected_count * reports_per_device
        completion_rate = (final_sent / expected_total * 100) if expected_total > 0 else 0
        
        logger.info(f"🎯 测试参数: {connected_count} 台设备, {test_minutes} 分钟")
        logger.info(f"   每台设备: {reports_per_device} 条点钞报告")  
        logger.info(f"   每条报告: {notes_per_report} 张钞票")
        logger.info(f"   总计处理: {connected_count * reports_per_device * notes_per_report} 张钞票")
        logger.info(f"⏱️ 实际测试时间: {actual_test_time:.1f} 分钟")
        logger.info(f"📤 消息发送: {final_sent}/{expected_total} ({completion_rate:.1f}%)")
        logger.info(f"✅ 发送成功率: {final_success_rate:.1f}% ({final_success}/{final_sent})")
        logger.info(f"📊 内存使用:")
        logger.info(f"   初始内存: {initial_memory['rss_mb']:.1f}MB")
        logger.info(f"   最终内存: {final_memory['rss_mb']:.1f}MB")
        logger.info(f"   总增长: {total_memory_growth:.1f}MB")
        logger.info(f"   平均每台设备: {total_memory_growth/connected_count:.3f}MB")
        
        # 8小时1000设备场景投影
        if connected_count > 0:
            memory_per_device = total_memory_growth / connected_count
            projected_1000_8h = memory_per_device * 1000
            
            logger.info("=" * 70)
            logger.info("🔮 1000台设备8小时场景投影:")
            logger.info(f"   预计总内存占用: {projected_1000_8h:.1f}MB ({projected_1000_8h/1024:.2f}GB)")
            logger.info(f"   每台设备内存开销: {memory_per_device:.3f}MB")
            
            # 给出评估建议
            if memory_per_device < 1:
                logger.info("✅ 内存效率优秀，每台设备占用 < 1MB")
            elif memory_per_device < 5:
                logger.info("✅ 内存效率良好，每台设备占用 1-5MB")
            else:
                logger.info("❌ 每台设备内存开销较高，需优化")
        
        logger.info("=" * 70)
        
        # 清理
        manager.stop_all_simulators()
        
    except Exception as e:
        logger.error(f"测试异常: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='快速内存占用测试')
    parser.add_argument("--mode", type=str, choices=['single', 'multi'], default='single', 
                       help="测试模式: single=单台设备持续发送, multi=多台设备测试")
    parser.add_argument("--devices", type=int, default=100, help="测试设备数量 (默认100，仅multi模式)")
    parser.add_argument("--minutes", type=int, default=10, help="持续发送时长分钟数 (默认10)")
    
    args = parser.parse_args()
    
    if args.mode == 'single':
        logger.info("🚀 启动单台设备持续发送内存测试")
        logger.info(f"📋 将用1台设备持续发送 {args.minutes} 分钟，每条200张钞票，不间断发送")
        try:
            run_single_device_memory_test(args.minutes, 0)  # 传入0作为占位符，实际不使用
        except KeyboardInterrupt:
            logger.info("\n⛔ 测试被用户中断")
        except Exception as e:
            logger.error(f"测试失败: {e}")
    else:
        logger.info("🚀 启动多台设备内存测试")  
        # 保持原有的多设备测试逻辑
        total_reports_per_device = 20
        try:
            run_quick_memory_test(args.devices, args.minutes, total_reports_per_device, 200)
        except KeyboardInterrupt:
            logger.info("\n⛔ 测试被用户中断")
        except Exception as e:
            logger.error(f"测试失败: {e}")


if __name__ == "__main__":
    main()
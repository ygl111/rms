#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合性能测试脚本
测试所有消息类型：注册、鉴权、心跳、故障上报、点钞上报
"""

import argparse
import time
import threading
import random
import logging
import queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from enhanced_device_simulator import EnhancedDeviceSimulator, DeviceSimulatorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('ComprehensivePerformanceTest')


class ComprehensivePerformanceTestRunner:
    """综合性能测试运行器"""
    
    def __init__(self, config_file: str = "test_config.json"):
        self.config_file = config_file
        self.manager = DeviceSimulatorManager(config_file)
        self.running = False
        # 记录全局测试起止（用于总测试时长显示）
        self.manager.global_test_start_time = None
        
    def run_basic_performance_test(self, device_count: int = 10, test_duration: int = 60, 
                                  device_prefix: str = "PERF_TEST", max_concurrent: int = 50):
        """基础性能测试：测试连接、注册、鉴权，并发送少量消息验证功能"""
        # 设置估算需要的保持时长
        self.manager.configured_test_duration = test_duration
        # 记录开始时间（仅第一次进入时）
        if not self.manager.global_test_start_time:
            self.manager.global_test_start_time = time.time()
        logger.info(f"🚀 开始基础性能测试 - {device_count} 台设备，测试 {test_duration} 秒，并发数 {max_concurrent}")
        
        # 加载测试设备
        device_configs = self.manager.load_test_devices(device_prefix, device_count)
        if len(device_configs) < device_count:
            logger.warning(f"只找到 {len(device_configs)} 台测试设备，少于请求的 {device_count} 台")
        
        # 创建设备仿真器
        self.manager.create_simulators(device_configs)
        
        # 启动设备模拟器（使用并发）
        logger.info(f"📡 开始并发连接设备...")
        start_time = time.time()
        results = self.manager.start_all_simulators(registration_interval=0.01, max_concurrent=max_concurrent)
        connection_time = time.time() - start_time
        
        logger.info(f"⚡ 连接完成 - 耗时 {connection_time:.2f}秒，速度 {device_count/connection_time:.1f} 设备/秒")
        
        if results['authenticated'] > 0:
            logger.info(f"✅ 基础连接完成 - 成功认证 {results['authenticated']} 台设备")
            
            # 发送测试消息以验证功能
            logger.info("📨 发送测试消息验证功能...")
            for i, simulator in enumerate(self.manager.simulators):
                if simulator.connected:
                    # 发送一次故障上报
                    simulator.send_fault_report(
                        event_code=1000 + i,
                        event_content=f"Basic test fault {i}"
                    )
                    time.sleep(0.5)  # 避免消息冲突
                    
                    # 发送一次点钞上报
                    simulator.send_banknote_report(total_notes=100 + i * 10)
                    time.sleep(0.5)
                    
                    # 发送一次心跳
                    simulator.send_heartbeat()
                    time.sleep(0.2)
            
            # 等待剩余测试时间
            remaining_time = max(0, test_duration - 30)  # 减去消息发送时间
            if remaining_time > 0:
                logger.info(f"⏰ 等待剩余测试时间 {remaining_time} 秒...")
                time.sleep(remaining_time)
            
            # 生成报告
            # 结束时间记录
            if not self.manager.global_test_end_time:
                self.manager.global_test_end_time = time.time()
                self.manager.global_test_duration = self.manager.global_test_end_time - self.manager.global_test_start_time
            report_file = self.manager.generate_simple_report()
            logger.info(f"📊 测试报告已生成: {report_file}")
            return True
        else:
            logger.error("❌ 基础性能测试失败 - 没有设备成功认证")
            return False
    
    def run_heartbeat_stress_test(self, device_count: int = 10, test_duration: int = 300, 
                                 heartbeat_interval: int = 10, max_concurrent: int = 50):
        """心跳压力测试"""
        self.manager.configured_test_duration = test_duration
        if not self.manager.global_test_start_time:
            self.manager.global_test_start_time = time.time()
        logger.info(f"💓 开始心跳压力测试 - {device_count} 台设备，心跳间隔 {heartbeat_interval} 秒，测试 {test_duration} 秒")
        
        # 加载并启动设备
        device_configs = self.manager.load_test_devices(limit=device_count)
        self.manager.create_simulators(device_configs)
        results = self.manager.start_all_simulators(registration_interval=0.01, max_concurrent=max_concurrent)
        
        if results['authenticated'] == 0:
            logger.error("❌ 设备连接失败，无法进行心跳测试")
            return False
        
        # 开始心跳循环测试
        start_time = time.time()
        self.running = True
        heartbeat_threads = []
        
        def heartbeat_worker(simulator: EnhancedDeviceSimulator):
            """心跳工作线程"""
            while self.running and (time.time() - start_time) < test_duration:
                if simulator.connected:
                    simulator.send_heartbeat()
                time.sleep(heartbeat_interval + random.uniform(-1, 1))  # 加入随机波动
        
        # 为每个设备启动心跳线程
        for simulator in self.manager.simulators:
            if simulator.connected:
                thread = threading.Thread(target=heartbeat_worker, args=(simulator,))
                thread.daemon = True
                thread.start()
                heartbeat_threads.append(thread)
        
        # 等待测试完成
        time.sleep(test_duration)
        self.running = False
        
        # 等待所有线程完成
        for thread in heartbeat_threads:
            thread.join(timeout=5)
        
        logger.info("✅ 心跳压力测试完成")
        if not self.manager.global_test_end_time:
            self.manager.global_test_end_time = time.time()
            self.manager.global_test_duration = self.manager.global_test_end_time - self.manager.global_test_start_time
        report_file = self.manager.generate_simple_report()
        logger.info(f"📊 心跳测试报告已生成: {report_file}")
        
        return True
    
    def run_message_burst_test(self, device_count: int = 10, test_duration: int = 180,
                              fault_interval: int = 30, banknote_interval: int = 45, max_concurrent: int = 50):
        """消息突发测试：定期发送故障上报和点钞上报"""
        self.manager.configured_test_duration = test_duration
        if not self.manager.global_test_start_time:
            self.manager.global_test_start_time = time.time()
        logger.info(f"📨 开始消息突发测试 - {device_count} 台设备，故障间隔 {fault_interval}s，点钞间隔 {banknote_interval}s")
        
        # 加载并启动设备
        device_configs = self.manager.load_test_devices(limit=device_count)
        self.manager.create_simulators(device_configs)
        results = self.manager.start_all_simulators(registration_interval=0.01, max_concurrent=max_concurrent)
        
        if results['authenticated'] == 0:
            logger.error("❌ 设备连接失败，无法进行消息测试")
            return False
        
        start_time = time.time()
        self.running = True
        message_threads = []
        
        def fault_report_worker(simulator: EnhancedDeviceSimulator):
            """故障上报工作线程"""
            while self.running and (time.time() - start_time) < test_duration:
                if simulator.connected:
                    event_code = random.randint(1000, 9999)
                    simulator.send_fault_report(
                        event_code=event_code,
                        event_content=f"Test fault {event_code} from {simulator.device_config.device_id}"
                    )
                time.sleep(fault_interval + random.uniform(-2, 2))
        
        def banknote_report_worker(simulator: EnhancedDeviceSimulator):
            """点钞上报工作线程"""
            while self.running and (time.time() - start_time) < test_duration:
                if simulator.connected:
                    total_notes = random.randint(50, 500)
                    simulator.send_banknote_report(total_notes=total_notes)
                time.sleep(banknote_interval + random.uniform(-3, 3))
        
        # 为每个设备启动消息发送线程
        for simulator in self.manager.simulators:
            if simulator.connected:
                # 故障上报线程
                fault_thread = threading.Thread(target=fault_report_worker, args=(simulator,))
                fault_thread.daemon = True
                fault_thread.start()
                message_threads.append(fault_thread)
                
                # 点钞上报线程
                banknote_thread = threading.Thread(target=banknote_report_worker, args=(simulator,))
                banknote_thread.daemon = True
                banknote_thread.start()
                message_threads.append(banknote_thread)
        
        # 等待测试完成
        time.sleep(test_duration)
        self.running = False
        
        # 等待所有线程完成
        for thread in message_threads:
            thread.join(timeout=5)
        
        logger.info("✅ 消息突发测试完成")
        if not self.manager.global_test_end_time:
            self.manager.global_test_end_time = time.time()
            self.manager.global_test_duration = self.manager.global_test_end_time - self.manager.global_test_start_time
        report_file = self.manager.generate_simple_report()
        logger.info(f"📊 消息测试报告已生成: {report_file}")
        
        return True
    
    def run_comprehensive_stress_test(self, device_count: int = 50, test_duration: int = 600, 
                                     device_prefix: str = "PERF_TEST", max_concurrent: int = 100,
                                     max_workers: int = 400, max_workers_cap: int = 800):
        """综合压力测试：同时测试所有消息类型 (优化版 - 解决线程爆炸问题)"""
        self.manager.configured_test_duration = test_duration
        if not self.manager.global_test_start_time:
            self.manager.global_test_start_time = time.time()
        logger.info(f"🔥 开始优化版综合压力测试 - {device_count} 台设备，测试 {test_duration} 秒")
        logger.info(f"🔧 线程优化: 使用 {max_workers} 工作线程 (替代 {device_count} 设备线程)")
        logger.info(f"⚡ 保持原有测试压力: 心跳20-40s, 故障60-120s, 点钞90-180s")
        
        # 加载并启动设备
        device_configs = self.manager.load_test_devices(device_prefix, device_count)
        self.manager.create_simulators(device_configs)
        
        # 使用并发连接
        logger.info(f"📡 开始并发连接设备...")
        start_time = time.time()
        results = self.manager.start_all_simulators(registration_interval=0.01, max_concurrent=max_concurrent)
        connection_time = time.time() - start_time
        
        logger.info(f"⚡ 连接完成 - 耗时 {connection_time:.2f}秒，速度 {device_count/connection_time:.1f} 设备/秒")
        
        if results['authenticated'] == 0:
            logger.error("❌ 设备连接失败，无法进行综合测试")
            return False
        
        start_time = time.time()
        self.running = True
        
        # 🚀 优化关键点：使用任务队列 + 线程池模式，避免万台设备创建万个线程
        task_queue = queue.Queue()
        
        def task_worker():
            """任务工作线程 - 处理来自队列的任务（自适应接收超时）"""
            while self.running:
                try:
                    task = task_queue.get(timeout=1)
                    if task is None:
                        break

                    simulator, task_type = task
                    if not simulator.connected:
                        task_queue.task_done()
                        continue

                    # 根据队列压力自适应增加接收超时（避免服务端忙时被判为超时）
                    qsize = task_queue.qsize()
                    if qsize > 5000:
                        recv_timeout = 12.0
                    elif qsize > 2000:
                        recv_timeout = 10.0
                    else:
                        recv_timeout = 8.0

                    try:
                        if task_type == 'heartbeat':
                            simulator.send_heartbeat()
                        elif task_type == 'fault':
                            event_code = random.randint(1000, 9999)
                            # 在高压时降低重试次数，快速让位
                            if qsize > 5000:
                                mr = 2
                            elif qsize > 3000:
                                mr = 3
                            else:
                                mr = 5
                            simulator.send_fault_report(
                                event_code=event_code,
                                event_content=f"Random fault {event_code}",
                                recv_timeout=recv_timeout,
                                max_retries=mr
                            )
                        elif task_type == 'banknote':
                            # 在高压时缩小 NOTE 明细，避免服务器负担过重
                            if qsize > 5000:
                                total_notes = random.randint(10, 50)
                                mr = 2
                            elif qsize > 3000:
                                total_notes = random.randint(50, 200)
                                mr = 3
                            else:
                                total_notes = random.randint(100, 800)
                                mr = 5
                            simulator.send_banknote_report(total_notes=total_notes, recv_timeout=recv_timeout, max_retries=mr)
                    except Exception as e:
                        logger.debug(f"任务执行失败: {e}")
                    finally:
                        task_queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"工作线程异常: {e}")
        
        # 启动固定数量的工作线程 (而不是为每个设备启动线程)
        worker_threads = []
        for _ in range(max_workers):
            thread = threading.Thread(target=task_worker, daemon=True)
            thread.start()
            worker_threads.append(thread)
            
        # 任务调度器 - 替代原来的每设备线程
        def task_scheduler():
            """任务调度器（平滑负载版）：按设备下次时间轮询 + 自适应节流，避免队列尖峰"""
            now = time.time()
            # 为每台设备生成固定的区间范围，避免每次循环都用新的随机起点导致“拥挤”
            hb_min, hb_max = 20, 40
            ft_min, ft_max = 60, 120
            bn_min, bn_max = 90, 180

            device_next_heartbeat = {}
            device_next_fault = {}
            device_next_banknote = {}
            for sim in self.manager.simulators:
                device_next_heartbeat[sim.device_config.device_id] = now + random.uniform(hb_min, hb_max)
                device_next_fault[sim.device_config.device_id] = now + random.uniform(ft_min, ft_max)
                device_next_banknote[sim.device_config.device_id] = now + random.uniform(bn_min, bn_max)

            # 基于队列压力的批量上限自适应策略
            def compute_batch_limit(qsize: int) -> int:
                if qsize > 5000:
                    return 100
                if qsize > 3000:
                    return 200
                if qsize > 1500:
                    return 350
                return 600

            while self.running and (time.time() - start_time) < test_duration:
                current_time = time.time()
                qsize = task_queue.qsize()
                batch_limit = compute_batch_limit(qsize)
                tasks_added = 0

                if qsize > 3000:
                    logger.warning(f"⚠️ 任务队列积压 ({qsize})，短暂降载...")
                    time.sleep(1)  # 缩短降载时间，提高回收速度

                # 在调度器内也快速扩容，避免等待进度线程
                if qsize > 1200 and len(worker_threads) < max_workers_cap:
                    if qsize > 4000:
                        step = 50
                    elif qsize > 2500:
                        step = 30
                    else:
                        step = 15
                    add = min(step, max_workers_cap - len(worker_threads))
                    if add > 0:
                        for _ in range(add):
                            t = threading.Thread(target=task_worker, daemon=True)
                            t.start()
                            worker_threads.append(t)
                        logger.info(f"🧰(调度器) 动态扩容工作线程: +{add} → {len(worker_threads)} (队列 {qsize})")

                for sim in self.manager.simulators:
                    if not sim.connected:
                        continue
                    did = sim.device_config.device_id

                    # 心跳到期
                    if current_time >= device_next_heartbeat[did]:
                        task_queue.put((sim, 'heartbeat'))
                        device_next_heartbeat[did] = current_time + random.uniform(hb_min, hb_max)
                        tasks_added += 1
                        if tasks_added >= batch_limit:
                            break

                    # 故障到期
                    if current_time >= device_next_fault[did]:
                        task_queue.put((sim, 'fault'))
                        device_next_fault[did] = current_time + random.uniform(ft_min, ft_max)
                        tasks_added += 1
                        if tasks_added >= batch_limit:
                            break

                    # 点钞到期
                    if current_time >= device_next_banknote[did]:
                        task_queue.put((sim, 'banknote'))
                        device_next_banknote[did] = current_time + random.uniform(bn_min, bn_max)
                        tasks_added += 1
                        if tasks_added >= batch_limit:
                            break

                # 调度器小歇：更短的间隔让到期任务更均匀分布
                time.sleep(1.0)
        
        # 启动调度器
        scheduler_thread = threading.Thread(target=task_scheduler, daemon=True)
        scheduler_thread.start()
        
        # 定期报告进度 (优化版)
        def progress_reporter():
            last_progress = time.time()
            while self.running:
                time.sleep(30)  # 每30秒报告一次，便于更快扩缩容
                if self.running:
                    current_time = time.time()
                    elapsed = current_time - start_time
                    remaining = test_duration - elapsed
                    queue_size = task_queue.qsize()
                    
                    logger.info(f"📊 测试进行中... 已运行 {elapsed:.0f}s，剩余 {remaining:.0f}s")
                    logger.info(f"🔧 任务队列大小: {queue_size} | 工作线程: {len(worker_threads)}")
                    
                    # 🚨 队列积压警告
                    if queue_size > 5000:
                        logger.error(f"🚨 严重警告：任务队列积压 {queue_size}，可能导致超时！")
                    elif queue_size > 1000:
                        logger.warning(f"⚠️ 队列积压警告：{queue_size} 个任务待处理")

                    # 动态扩容工作线程（在系统空闲时扩大吞吐）
                    try:
                        # 更积极：当队列>1500就尝试扩容，步长根据压力变化
                        if queue_size > 1500 and len(worker_threads) < max_workers_cap:
                            if queue_size > 4000:
                                step = 50
                            elif queue_size > 2500:
                                step = 30
                            else:
                                step = 20
                            add = min(step, max_workers_cap - len(worker_threads))
                            if add > 0:
                                for _ in range(add):
                                    t = threading.Thread(target=task_worker, daemon=True)
                                    t.start()
                                    worker_threads.append(t)
                                logger.info(f"🧰 动态扩容工作线程: +{add} → {len(worker_threads)} (队列 {queue_size})")
                    except Exception as e:
                        logger.debug(f"动态扩容失败: {e}")
                    
                    # 打印当前统计
                    stats_list = self.manager.get_all_stats()
                    connected_count = sum(1 for s in stats_list if s['connected'])
                    total_heartbeat = sum(s.get('heartbeat_sent', 0) for s in stats_list)
                    total_fault = sum(s.get('fault_reports_sent', 0) for s in stats_list)
                    total_banknote = sum(s.get('banknote_reports_sent', 0) for s in stats_list)
                    
                    # 计算成功率
                    total_sent = total_heartbeat + total_fault + total_banknote
                    throughput = total_sent / elapsed if elapsed > 0 else 0
                    
                    logger.info(f"   📈 在线设备: {connected_count}/{len(stats_list)}")
                    logger.info(f"   💓 心跳总数: {total_heartbeat}")
                    logger.info(f"   🚨 故障上报: {total_fault}")
                    logger.info(f"   💰 点钞上报: {total_banknote}")
                    logger.info(f"   🚀 吞吐量: {throughput:.1f} 消息/秒")
        
        # 启动进度线程
        progress_thread = threading.Thread(target=progress_reporter)
        progress_thread.daemon = True
        progress_thread.start()
        
        # 等待测试完成
        logger.info(f"⏰ 测试运行中，将持续 {test_duration} 秒...")
        time.sleep(test_duration)
        
        # 停止所有线程
        self.running = False
        
        # 发送停止信号给所有工作线程（包含动态扩容后的数量）
        for _ in range(len(worker_threads)):
            task_queue.put(None)
        
        # 等待线程完成 (优化版)
        for thread in worker_threads:
            thread.join(timeout=5)
        scheduler_thread.join(timeout=5)
        progress_thread.join(timeout=5)
        
        logger.info("✅ 综合压力测试完成")
        if not self.manager.global_test_end_time:
            self.manager.global_test_end_time = time.time()
            self.manager.global_test_duration = self.manager.global_test_end_time - self.manager.global_test_start_time
        report_file = self.manager.generate_simple_report()
        logger.info(f"📊 综合测试报告已生成: {report_file}")
        
        return True
    
    def cleanup(self):
        """清理资源"""
        self.running = False
        if hasattr(self, 'manager'):
            self.manager.stop_all_simulators()


def main():
    parser = argparse.ArgumentParser(description="综合性能测试工具")
    parser.add_argument("--test-type", choices=["basic", "heartbeat", "message", "comprehensive"], 
                       default="basic", help="测试类型")
    parser.add_argument("--devices", type=int, default=10, help="设备数量")
    parser.add_argument("--duration", type=int, default=60, help="测试时长(秒)")
    parser.add_argument("--heartbeat-interval", type=int, default=30, help="心跳间隔(秒)")
    parser.add_argument("--fault-interval", type=int, default=60, help="故障上报间隔(秒)")
    parser.add_argument("--banknote-interval", type=int, default=90, help="点钞上报间隔(秒)")
    parser.add_argument("--device-prefix", type=str, default="PERF_TEST", help="设备ID前缀")
    parser.add_argument("--max-concurrent", type=int, default=100, help="最大并发连接数")
    parser.add_argument("--max-workers", type=int, default=400, help="最大工作线程数 (系统空闲时直接用大值避免动态扩容延迟)")
    parser.add_argument("--max-workers-cap", type=int, default=800, help="动态扩容的工作线程上限")
    parser.add_argument("--config", default="test_config.json", help="配置文件")
    
    args = parser.parse_args()
    
    runner = ComprehensivePerformanceTestRunner(args.config)
    
    try:
        if args.test_type == "basic":
            success = runner.run_basic_performance_test(args.devices, args.duration, 
                                                       args.device_prefix, args.max_concurrent)
        elif args.test_type == "heartbeat":
            success = runner.run_heartbeat_stress_test(args.devices, args.duration, 
                                                      args.heartbeat_interval, args.max_concurrent)
        elif args.test_type == "message":
            success = runner.run_message_burst_test(args.devices, args.duration, 
                                                   args.fault_interval, args.banknote_interval, args.max_concurrent)
        elif args.test_type == "comprehensive":
            success = runner.run_comprehensive_stress_test(args.devices, args.duration, 
                                                          args.device_prefix, args.max_concurrent,
                                                          args.max_workers, args.max_workers_cap)
        
        if success:
            logger.info("🎉 性能测试成功完成！")
        else:
            logger.error("💥 性能测试失败！")
            
    except KeyboardInterrupt:
        logger.info("🛑 测试被用户中断")
    except Exception as e:
        logger.error(f"💥 测试过程中发生错误: {e}")
    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()
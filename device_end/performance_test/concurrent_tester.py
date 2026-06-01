#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并发测试模块
专门用于测试大量并发连接的性能
"""

import threading
import time
import random
import queue
import json
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from device_simulator import DeviceSimulator, DeviceConfig, ConnectionConfig
from load_tester import TestResult, PerformanceMonitor
import logging

logger = logging.getLogger('ConcurrentTester')


@dataclass
class ConcurrentTestConfig:
    """并发测试配置"""
    host: str = "127.0.0.1"
    port: int = 8081
    
    # 并发测试参数
    max_concurrent_connections: int = 1000    # 最大并发连接数
    connection_ramp_rate: float = 10.0        # 连接建立速率 (connections/second)
    hold_time: int = 60                       # 连接保持时间 (seconds)
    
    # 消息发送参数
    messages_per_connection: int = 10         # 每个连接发送的消息数
    message_send_rate: float = 1.0           # 消息发送速率 (messages/second)
    
    # 连接模式
    connection_pattern: str = "burst"         # "burst", "gradual", "wave"
    
    # 测试场景
    test_scenarios: List[str] = None         # 测试场景列表
    
    def __post_init__(self):
        if self.test_scenarios is None:
            self.test_scenarios = ["connect_only", "connect_and_send", "long_lived"]


class ConnectionManager:
    """连接管理器 - 管理大量并发连接"""
    
    def __init__(self, config: ConcurrentTestConfig):
        self.config = config
        self.connections: Dict[str, DeviceSimulator] = {}
        self.connection_stats: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.monitor = PerformanceMonitor()
        
    def create_connection(self, device_id: str) -> Optional[DeviceSimulator]:
        """创建单个连接"""
        device_config = DeviceConfig(
            device_id=device_id,
            manufacturer="ConcurrentTest",
            device_type=random.randint(1, 3),
            device_model=f"CT-{random.randint(1000, 9999)}"
        )
        
        connection_config = ConnectionConfig(
            host=self.config.host,
            port=self.config.port,
            timeout=10,
            reconnect_interval=1,
            max_reconnect_attempts=1
        )
        
        simulator = DeviceSimulator(device_config, connection_config)
        
        start_time = time.time()
        if simulator.connect():
            connection_time = time.time() - start_time
            
            with self.lock:
                self.connections[device_id] = simulator
                self.connection_stats[device_id] = {
                    'connected_at': start_time,
                    'connection_time': connection_time,
                    'messages_sent': 0,
                    'messages_received': 0,
                    'errors': 0,
                    'last_activity': start_time
                }
            
            self.monitor.record_response(connection_time)
            logger.debug(f"连接 {device_id} 建立成功，耗时 {connection_time:.3f}s")
            return simulator
        else:
            self.monitor.record_error(f"Connection failed for {device_id}")
            logger.warning(f"连接 {device_id} 建立失败")
            return None
    
    def close_connection(self, device_id: str):
        """关闭单个连接"""
        with self.lock:
            if device_id in self.connections:
                simulator = self.connections[device_id]
                simulator.disconnect()
                del self.connections[device_id]
                
                if device_id in self.connection_stats:
                    self.connection_stats[device_id]['disconnected_at'] = time.time()
    
    def close_all_connections(self):
        """关闭所有连接"""
        with self.lock:
            for device_id, simulator in self.connections.items():
                simulator.disconnect()
            self.connections.clear()
    
    def get_active_connection_count(self) -> int:
        """获取活跃连接数"""
        with self.lock:
            return len(self.connections)
    
    def send_message_to_device(self, device_id: str, message_type: str = "heartbeat") -> bool:
        """向指定设备发送消息"""
        with self.lock:
            if device_id not in self.connections:
                return False
            
            simulator = self.connections[device_id]
        
        start_time = time.time()
        success = False
        
        try:
            if message_type == "heartbeat":
                success = simulator.send_heartbeat()
            elif message_type == "banknote_report":
                success = simulator.send_banknote_report()
            elif message_type == "fault_report":
                success = simulator.send_fault_report()
            
            if success:
                response_time = time.time() - start_time
                self.monitor.record_response(response_time)
                
                with self.lock:
                    if device_id in self.connection_stats:
                        self.connection_stats[device_id]['messages_sent'] += 1
                        self.connection_stats[device_id]['last_activity'] = time.time()
            else:
                self.monitor.record_error(f"Message send failed for {device_id}")
                with self.lock:
                    if device_id in self.connection_stats:
                        self.connection_stats[device_id]['errors'] += 1
        
        except Exception as e:
            self.monitor.record_error(f"Exception sending message to {device_id}: {str(e)}")
            with self.lock:
                if device_id in self.connection_stats:
                    self.connection_stats[device_id]['errors'] += 1
        
        return success


class ConcurrentTester:
    """并发测试器"""
    
    def __init__(self, config: ConcurrentTestConfig):
        self.config = config
        self.connection_manager = ConnectionManager(config)
        self.running = False
        self.test_results = []
    
    def _connection_burst_pattern(self) -> List[float]:
        """突发连接模式 - 快速建立所有连接"""
        interval = 1.0 / self.config.connection_ramp_rate
        return [interval] * self.config.max_concurrent_connections
    
    def _connection_gradual_pattern(self) -> List[float]:
        """渐进连接模式 - 逐步增加连接"""
        total_time = self.config.max_concurrent_connections / self.config.connection_ramp_rate
        intervals = []
        for i in range(self.config.max_concurrent_connections):
            # 连接间隔逐渐减少
            progress = i / self.config.max_concurrent_connections
            interval = (1.0 / self.config.connection_ramp_rate) * (1 + progress)
            intervals.append(interval)
        return intervals
    
    def _connection_wave_pattern(self) -> List[float]:
        """波浪连接模式 - 波浪式建立连接"""
        import math
        intervals = []
        for i in range(self.config.max_concurrent_connections):
            # 使用正弦波模式
            wave_factor = (math.sin(i * 0.1) + 1) / 2 + 0.1  # 0.1 到 1.1 之间
            interval = (1.0 / self.config.connection_ramp_rate) * wave_factor
            intervals.append(interval)
        return intervals
    
    def _get_connection_intervals(self) -> List[float]:
        """根据模式获取连接间隔"""
        if self.config.connection_pattern == "gradual":
            return self._connection_gradual_pattern()
        elif self.config.connection_pattern == "wave":
            return self._connection_wave_pattern()
        else:  # burst
            return self._connection_burst_pattern()
    
    def test_connection_only(self) -> TestResult:
        """测试场景1: 仅建立连接"""
        logger.info("开始连接测试: 仅建立连接")
        
        start_time = time.time()
        self.connection_manager.monitor.reset()
        
        intervals = self._get_connection_intervals()
        
        # 使用线程池建立连接
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            
            for i in range(self.config.max_concurrent_connections):
                device_id = f"CONN_TEST_{i:04d}"
                
                # 按照间隔提交连接任务
                if i > 0:
                    time.sleep(intervals[i-1])
                
                future = executor.submit(self.connection_manager.create_connection, device_id)
                futures.append((device_id, future))
            
            # 等待所有连接建立完成
            successful_connections = 0
            for device_id, future in futures:
                try:
                    result = future.result(timeout=30)
                    if result:
                        successful_connections += 1
                except Exception as e:
                    logger.error(f"连接 {device_id} 异常: {e}")
        
        # 保持连接一段时间
        logger.info(f"保持 {successful_connections} 个连接 {self.config.hold_time} 秒")
        time.sleep(self.config.hold_time)
        
        # 关闭所有连接
        self.connection_manager.close_all_connections()
        
        end_time = time.time()
        stats = self.connection_manager.monitor.get_stats()
        
        return TestResult(
            test_name="Connection Only Test",
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            total_devices=self.config.max_concurrent_connections,
            successful_connections=successful_connections,
            failed_connections=self.config.max_concurrent_connections - successful_connections,
            total_messages_sent=0,
            total_messages_received=0,
            total_errors=stats['error_count'],
            messages_per_second=0,
            avg_response_time=stats['avg_response_time'],
            min_response_time=stats['min_response_time'],
            max_response_time=stats['max_response_time'],
            p95_response_time=stats['p95_response_time'],
            p99_response_time=stats['p99_response_time'],
            connection_success_rate=successful_connections / self.config.max_concurrent_connections,
            message_success_rate=1.0,
            response_times=self.connection_manager.monitor.response_times.copy(),
            error_details=[],
            device_stats=list(self.connection_manager.connection_stats.values())
        )
    
    def test_connect_and_send(self) -> TestResult:
        """测试场景2: 建立连接并发送消息"""
        logger.info("开始连接和发送测试")
        
        start_time = time.time()
        self.connection_manager.monitor.reset()
        
        # 先建立连接
        successful_connections = 0
        intervals = self._get_connection_intervals()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            connection_futures = []
            
            for i in range(self.config.max_concurrent_connections):
                device_id = f"SEND_TEST_{i:04d}"
                
                if i > 0:
                    time.sleep(intervals[i-1])
                
                future = executor.submit(self.connection_manager.create_connection, device_id)
                connection_futures.append((device_id, future))
            
            # 收集成功的连接
            connected_devices = []
            for device_id, future in connection_futures:
                try:
                    result = future.result(timeout=30)
                    if result:
                        connected_devices.append(device_id)
                        successful_connections += 1
                except Exception as e:
                    logger.error(f"连接 {device_id} 异常: {e}")
        
        logger.info(f"成功建立 {successful_connections} 个连接，开始发送消息")
        
        # 发送消息
        message_send_interval = 1.0 / self.config.message_send_rate
        
        def send_messages_worker(device_id: str):
            """发送消息的工作线程"""
            for i in range(self.config.messages_per_connection):
                message_types = ["heartbeat", "banknote_report", "fault_report"]
                message_type = random.choice(message_types)
                
                self.connection_manager.send_message_to_device(device_id, message_type)
                
                if i < self.config.messages_per_connection - 1:
                    time.sleep(message_send_interval)
        
        # 并发发送消息
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(connected_devices)) as executor:
            message_futures = [
                executor.submit(send_messages_worker, device_id) 
                for device_id in connected_devices
            ]
            
            # 等待所有消息发送完成
            for future in concurrent.futures.as_completed(message_futures, timeout=300):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"消息发送异常: {e}")
        
        # 关闭连接
        self.connection_manager.close_all_connections()
        
        end_time = time.time()
        stats = self.connection_manager.monitor.get_stats()
        
        total_messages_sent = sum(
            device_stat['messages_sent'] 
            for device_stat in self.connection_manager.connection_stats.values()
        )
        
        return TestResult(
            test_name="Connect and Send Test",
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            total_devices=self.config.max_concurrent_connections,
            successful_connections=successful_connections,
            failed_connections=self.config.max_concurrent_connections - successful_connections,
            total_messages_sent=total_messages_sent,
            total_messages_received=stats['success_count'],
            total_errors=stats['error_count'],
            messages_per_second=stats['qps'],
            avg_response_time=stats['avg_response_time'],
            min_response_time=stats['min_response_time'],
            max_response_time=stats['max_response_time'],
            p95_response_time=stats['p95_response_time'],
            p99_response_time=stats['p99_response_time'],
            connection_success_rate=successful_connections / self.config.max_concurrent_connections,
            message_success_rate=stats['success_rate'],
            response_times=self.connection_manager.monitor.response_times.copy(),
            error_details=[],
            device_stats=list(self.connection_manager.connection_stats.values())
        )
    
    def test_long_lived_connections(self) -> TestResult:
        """测试场景3: 长期保持连接"""
        logger.info("开始长期连接测试")
        
        start_time = time.time()
        self.connection_manager.monitor.reset()
        self.running = True
        
        # 建立连接
        successful_connections = 0
        connected_devices = []
        
        for i in range(self.config.max_concurrent_connections):
            device_id = f"LONG_TEST_{i:04d}"
            
            if self.connection_manager.create_connection(device_id):
                connected_devices.append(device_id)
                successful_connections += 1
            
            # 控制连接建立速率
            time.sleep(1.0 / self.config.connection_ramp_rate)
        
        logger.info(f"建立 {successful_connections} 个长期连接")
        
        # 定期发送消息维持连接
        def heartbeat_worker():
            """心跳工作线程"""
            while self.running:
                for device_id in connected_devices:
                    if not self.running:
                        break
                    self.connection_manager.send_message_to_device(device_id, "heartbeat")
                
                time.sleep(30)  # 每30秒发送一次心跳
        
        # 启动心跳线程
        heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        heartbeat_thread.start()
        
        # 保持连接指定时间
        time.sleep(self.config.hold_time)
        
        # 停止测试
        self.running = False
        heartbeat_thread.join(timeout=5)
        
        # 关闭连接
        self.connection_manager.close_all_connections()
        
        end_time = time.time()
        stats = self.connection_manager.monitor.get_stats()
        
        total_messages_sent = sum(
            device_stat['messages_sent'] 
            for device_stat in self.connection_manager.connection_stats.values()
        )
        
        return TestResult(
            test_name="Long Lived Connections Test",
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            total_devices=self.config.max_concurrent_connections,
            successful_connections=successful_connections,
            failed_connections=self.config.max_concurrent_connections - successful_connections,
            total_messages_sent=total_messages_sent,
            total_messages_received=stats['success_count'],
            total_errors=stats['error_count'],
            messages_per_second=stats['qps'],
            avg_response_time=stats['avg_response_time'],
            min_response_time=stats['min_response_time'],
            max_response_time=stats['max_response_time'],
            p95_response_time=stats['p95_response_time'],
            p99_response_time=stats['p99_response_time'],
            connection_success_rate=successful_connections / self.config.max_concurrent_connections,
            message_success_rate=stats['success_rate'],
            response_times=self.connection_manager.monitor.response_times.copy(),
            error_details=[],
            device_stats=list(self.connection_manager.connection_stats.values())
        )
    
    def run_all_scenarios(self) -> List[TestResult]:
        """运行所有测试场景"""
        results = []
        
        for scenario in self.config.test_scenarios:
            logger.info(f"运行测试场景: {scenario}")
            
            # 重置连接管理器
            self.connection_manager = ConnectionManager(self.config)
            
            try:
                if scenario == "connect_only":
                    result = self.test_connection_only()
                elif scenario == "connect_and_send":
                    result = self.test_connect_and_send()
                elif scenario == "long_lived":
                    result = self.test_long_lived_connections()
                else:
                    logger.warning(f"未知测试场景: {scenario}")
                    continue
                
                results.append(result)
                logger.info(f"场景 {scenario} 完成: 连接成功率={result.connection_success_rate:.2%}, "
                           f"消息成功率={result.message_success_rate:.2%}")
                
            except Exception as e:
                logger.error(f"场景 {scenario} 执行失败: {e}")
            
            # 场景间休息
            time.sleep(5)
        
        return results


if __name__ == "__main__":
    # 测试配置
    config = ConcurrentTestConfig(
        host="127.0.0.1",
        port=8081,
        max_concurrent_connections=50,
        connection_ramp_rate=5.0,
        hold_time=30,
        messages_per_connection=5,
        message_send_rate=2.0,
        connection_pattern="burst",
        test_scenarios=["connect_only", "connect_and_send"]
    )
    
    # 运行并发测试
    tester = ConcurrentTester(config)
    results = tester.run_all_scenarios()
    
    # 输出结果
    for result in results:
        print(f"\n{result.test_name} 结果:")
        print(f"  总连接数: {result.total_devices}")
        print(f"  成功连接: {result.successful_connections}")
        print(f"  连接成功率: {result.connection_success_rate:.2%}")
        print(f"  消息发送: {result.total_messages_sent}")
        print(f"  消息成功率: {result.message_success_rate:.2%}")
        print(f"  平均响应时间: {result.avg_response_time*1000:.2f}ms")
        print(f"  P95响应时间: {result.p95_response_time*1000:.2f}ms")
    
    # 保存结果
    results_data = [result.to_dict() for result in results]
    with open("concurrent_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)
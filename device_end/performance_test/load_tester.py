#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
负载和压力测试模块
用于测试TCP Gateway和C++ Parser的性能
"""

import threading
import time
import random
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from device_simulator import DeviceSimulator, DeviceConfig, ConnectionConfig, MessageType
import logging

logger = logging.getLogger('LoadTester')


@dataclass
class TestConfig:
    """测试配置"""
    # 连接配置
    host: str = "127.0.0.1"
    port: int = 8081
    
    # 负载测试配置
    concurrent_devices: int = 10        # 并发设备数
    test_duration: int = 60            # 测试持续时间（秒）
    message_interval: float = 1.0      # 消息发送间隔（秒）
    ramp_up_time: int = 10             # 渐增时间（秒）
    
    # 消息类型权重（决定发送哪种消息的概率）
    message_weights: Dict[str, float] = None
    
    # 性能阈值
    max_response_time: float = 1.0     # 最大响应时间（秒）
    min_success_rate: float = 0.95     # 最小成功率
    
    # 其他配置
    heartbeat_interval: int = 30       # 心跳间隔
    reconnect_on_failure: bool = True  # 失败时重连
    
    def __post_init__(self):
        if self.message_weights is None:
            self.message_weights = {
                'heartbeat': 0.5,
                'banknote_report': 0.3,
                'fault_report': 0.2
            }


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    start_time: float
    end_time: float
    duration: float
    
    # 基本统计
    total_devices: int
    successful_connections: int
    failed_connections: int
    
    # 消息统计
    total_messages_sent: int
    total_messages_received: int
    total_errors: int
    
    # 性能指标
    messages_per_second: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    
    # 成功率
    connection_success_rate: float
    message_success_rate: float
    
    # 详细统计
    response_times: List[float]
    error_details: List[str]
    device_stats: List[Dict]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        # 移除大量数据，避免JSON过大
        if len(result['response_times']) > 1000:
            result['response_times'] = result['response_times'][:1000]
        if len(result['error_details']) > 100:
            result['error_details'] = result['error_details'][:100]
        return result


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置监控数据"""
        self.response_times = []
        self.error_count = 0
        self.success_count = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
    
    def record_response(self, response_time: float):
        """记录响应时间"""
        with self.lock:
            self.response_times.append(response_time)
            self.success_count += 1
    
    def record_error(self, error_msg: str = ""):
        """记录错误"""
        with self.lock:
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            if not self.response_times:
                return {
                    'total_requests': self.success_count + self.error_count,
                    'success_count': self.success_count,
                    'error_count': self.error_count,
                    'success_rate': 0.0,
                    'avg_response_time': 0.0,
                    'min_response_time': 0.0,
                    'max_response_time': 0.0,
                    'p95_response_time': 0.0,
                    'p99_response_time': 0.0,
                    'qps': 0.0
                }
            
            elapsed_time = time.time() - self.start_time
            total_requests = self.success_count + self.error_count
            
            return {
                'total_requests': total_requests,
                'success_count': self.success_count,
                'error_count': self.error_count,
                'success_rate': self.success_count / total_requests if total_requests > 0 else 0.0,
                'avg_response_time': statistics.mean(self.response_times),
                'min_response_time': min(self.response_times),
                'max_response_time': max(self.response_times),
                'p95_response_time': statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) > 20 else max(self.response_times),
                'p99_response_time': statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) > 100 else max(self.response_times),
                'qps': total_requests / elapsed_time if elapsed_time > 0 else 0.0
            }


class LoadTester:
    """负载测试器"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.monitor = PerformanceMonitor()
        self.devices: List[DeviceSimulator] = []
        self.running = False
        self.stop_event = threading.Event()
        
    def _create_device(self, device_id: str) -> DeviceSimulator:
        """创建设备仿真器"""
        device_config = DeviceConfig(
            device_id=device_id,
            manufacturer="LoadTest",
            device_type=random.randint(1, 3),
            device_model=f"LT-{random.randint(1000, 9999)}",
            firmware_version=f"1.{random.randint(0, 9)}.{random.randint(0, 9)}"
        )
        
        connection_config = ConnectionConfig(
            host=self.config.host,
            port=self.config.port,
            timeout=30,
            reconnect_interval=5,
            max_reconnect_attempts=3
        )
        
        return DeviceSimulator(device_config, connection_config)
    
    def _device_worker(self, device: DeviceSimulator, worker_id: int) -> Dict[str, Any]:
        """设备工作线程"""
        logger.info(f"设备 {device.device_config.device_id} 开始工作")
        
        device_stats = {
            'device_id': device.device_config.device_id,
            'worker_id': worker_id,
            'connected': False,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0,
            'start_time': time.time(),
            'connection_attempts': 0
        }
        
        try:
            # 建立连接
            device_stats['connection_attempts'] = 1
            if not device.connect():
                device_stats['errors'] += 1
                self.monitor.record_error("Connection failed")
                return device_stats
            
            device_stats['connected'] = True
            
            # 执行注册和鉴权
            start_time = time.time()
            if device.perform_registration():
                self.monitor.record_response(time.time() - start_time)
                device_stats['messages_sent'] += 1
                device_stats['messages_received'] += 1
            else:
                self.monitor.record_error("Registration failed")
                device_stats['errors'] += 1
                return device_stats
            
            start_time = time.time()
            if device.perform_authentication():
                self.monitor.record_response(time.time() - start_time)
                device_stats['messages_sent'] += 1
                device_stats['messages_received'] += 1
            else:
                self.monitor.record_error("Authentication failed")
                device_stats['errors'] += 1
                return device_stats
            
            # 启动心跳
            device.start_heartbeat_loop(self.config.heartbeat_interval)
            
            # 发送测试消息
            last_message_time = time.time()
            while self.running and not self.stop_event.is_set():
                current_time = time.time()
                
                # 检查是否到了发送消息的时间
                if current_time - last_message_time >= self.config.message_interval:
                    # 根据权重随机选择消息类型
                    message_type = self._choose_message_type()
                    
                    start_time = time.time()
                    success = False
                    
                    try:
                        if message_type == 'heartbeat':
                            success = device.send_heartbeat()
                        elif message_type == 'banknote_report':
                            success = device.send_banknote_report(
                                total_notes=random.randint(1, 1000)
                            )
                        elif message_type == 'fault_report':
                            success = device.send_fault_report(
                                event_code=random.randint(1000, 9999),
                                event_content=f"Load test fault {random.randint(1, 100)}"
                            )
                        
                        if success:
                            response_time = time.time() - start_time
                            self.monitor.record_response(response_time)
                            device_stats['messages_sent'] += 1
                        else:
                            self.monitor.record_error(f"Failed to send {message_type}")
                            device_stats['errors'] += 1
                    
                    except Exception as e:
                        self.monitor.record_error(f"Exception in {message_type}: {str(e)}")
                        device_stats['errors'] += 1
                    
                    last_message_time = current_time
                
                # 短暂休眠避免过度占用CPU
                time.sleep(0.01)
        
        except Exception as e:
            logger.error(f"设备 {device.device_config.device_id} 异常: {e}")
            device_stats['errors'] += 1
            self.monitor.record_error(f"Device exception: {str(e)}")
        
        finally:
            device.running = False
            device.disconnect()
            device_stats['end_time'] = time.time()
            device_stats['duration'] = device_stats['end_time'] - device_stats['start_time']
        
        return device_stats
    
    def _choose_message_type(self) -> str:
        """根据权重选择消息类型"""
        weights = self.config.message_weights
        choices = list(weights.keys())
        weights_list = list(weights.values())
        
        return random.choices(choices, weights=weights_list)[0]
    
    def run_load_test(self) -> TestResult:
        """运行负载测试"""
        logger.info(f"开始负载测试: {self.config.concurrent_devices} 并发设备, {self.config.test_duration}秒")
        
        start_time = time.time()
        self.monitor.reset()
        self.running = True
        self.stop_event.clear()
        
        # 创建设备
        self.devices = []
        for i in range(self.config.concurrent_devices):
            device_id = f"LOAD_TEST_DEVICE_{i:03d}"
            device = self._create_device(device_id)
            self.devices.append(device)
        
        # 使用线程池执行测试
        device_results = []
        with ThreadPoolExecutor(max_workers=self.config.concurrent_devices) as executor:
            # 渐增启动设备
            futures = []
            for i, device in enumerate(self.devices):
                if self.config.ramp_up_time > 0:
                    delay = i * (self.config.ramp_up_time / self.config.concurrent_devices)
                    time.sleep(delay)
                
                future = executor.submit(self._device_worker, device, i)
                futures.append(future)
            
            # 等待测试持续时间
            time.sleep(self.config.test_duration - self.config.ramp_up_time)
            
            # 停止测试
            logger.info("停止负载测试...")
            self.running = False
            self.stop_event.set()
            
            # 收集结果
            for future in as_completed(futures, timeout=30):
                try:
                    result = future.result()
                    device_results.append(result)
                except Exception as e:
                    logger.error(f"获取设备结果失败: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 计算最终结果
        stats = self.monitor.get_stats()
        
        successful_connections = sum(1 for r in device_results if r['connected'])
        failed_connections = len(device_results) - successful_connections
        
        total_messages_sent = sum(r['messages_sent'] for r in device_results)
        total_errors = sum(r['errors'] for r in device_results)
        
        # 创建测试结果
        result = TestResult(
            test_name="Load Test",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            total_devices=self.config.concurrent_devices,
            successful_connections=successful_connections,
            failed_connections=failed_connections,
            total_messages_sent=total_messages_sent,
            total_messages_received=stats['success_count'],
            total_errors=total_errors,
            messages_per_second=stats['qps'],
            avg_response_time=stats['avg_response_time'],
            min_response_time=stats['min_response_time'],
            max_response_time=stats['max_response_time'],
            p95_response_time=stats['p95_response_time'],
            p99_response_time=stats['p99_response_time'],
            connection_success_rate=successful_connections / self.config.concurrent_devices,
            message_success_rate=stats['success_rate'],
            response_times=self.monitor.response_times.copy(),
            error_details=[],  # 可以添加详细错误信息
            device_stats=device_results
        )
        
        logger.info(f"负载测试完成: QPS={result.messages_per_second:.2f}, "
                   f"平均响应时间={result.avg_response_time*1000:.2f}ms, "
                   f"成功率={result.message_success_rate:.2%}")
        
        return result


class StressTester(LoadTester):
    """压力测试器 - 逐步增加负载直到系统达到极限"""
    
    def __init__(self, config: TestConfig):
        super().__init__(config)
        self.stress_results = []
    
    def run_stress_test(self, start_devices: int = 1, max_devices: int = 100, 
                       step_size: int = 10, step_duration: int = 60) -> List[TestResult]:
        """运行压力测试"""
        logger.info(f"开始压力测试: {start_devices} -> {max_devices} 设备, 步长={step_size}")
        
        self.stress_results = []
        current_devices = start_devices
        
        while current_devices <= max_devices:
            logger.info(f"压力测试阶段: {current_devices} 并发设备")
            
            # 更新配置
            self.config.concurrent_devices = current_devices
            self.config.test_duration = step_duration
            
            # 运行测试
            result = self.run_load_test()
            result.test_name = f"Stress Test - {current_devices} devices"
            self.stress_results.append(result)
            
            # 检查是否达到性能阈值
            if (result.message_success_rate < self.config.min_success_rate or 
                result.avg_response_time > self.config.max_response_time):
                logger.warning(f"性能阈值达到: 成功率={result.message_success_rate:.2%}, "
                             f"响应时间={result.avg_response_time*1000:.2f}ms")
                break
            
            current_devices += step_size
            
            # 短暂休息后继续下一轮
            time.sleep(5)
        
        return self.stress_results


if __name__ == "__main__":
    # 测试配置
    test_config = TestConfig(
        host="127.0.0.1",
        port=8081,
        concurrent_devices=5,
        test_duration=30,
        message_interval=2.0,
        ramp_up_time=5
    )
    
    # 运行负载测试
    load_tester = LoadTester(test_config)
    result = load_tester.run_load_test()
    
    print("负载测试结果:")
    print(f"  总设备数: {result.total_devices}")
    print(f"  成功连接: {result.successful_connections}")
    print(f"  消息发送: {result.total_messages_sent}")
    print(f"  消息接收: {result.total_messages_received}")
    print(f"  QPS: {result.messages_per_second:.2f}")
    print(f"  平均响应时间: {result.avg_response_time*1000:.2f}ms")
    print(f"  P95响应时间: {result.p95_response_time*1000:.2f}ms")
    print(f"  成功率: {result.message_success_rate:.2%}")
    
    # 保存结果
    with open("load_test_result.json", "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
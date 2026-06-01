#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主性能测试脚本
集成所有测试模块，提供完整的性能测试套件
"""

import os
import sys
import argparse
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

# 导入测试模块
from device_simulator import DeviceSimulator, DeviceConfig, ConnectionConfig
from load_tester import LoadTester, StressTester, TestConfig, TestResult
from concurrent_tester import ConcurrentTester, ConcurrentTestConfig
from performance_monitor import (
    SystemMonitor, RedisMonitor, DatabaseMonitor, ApplicationMonitor,
    PerformanceReportGenerator
)

# 配置日志
def setup_logging(level: str = "INFO", log_file: str = "performance_test.log"):
    """设置日志配置"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

logger = logging.getLogger('MainTestRunner')


class TestRunner:
    """主测试运行器"""
    
    def __init__(self, config_file: str = "test_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self.test_results: List[Dict] = []
        
        # 监控器
        self.system_monitor: Optional[SystemMonitor] = None
        self.redis_monitor: Optional[RedisMonitor] = None
        self.database_monitor: Optional[DatabaseMonitor] = None
        self.application_monitor: Optional[ApplicationMonitor] = None
        
        # 测试运行状态
        self.running = False
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
    def _load_config(self) -> Dict[str, Any]:
        """加载测试配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"配置文件加载成功: {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def _get_environment_config(self, env_name: str = "local") -> Dict[str, Any]:
        """获取环境配置"""
        environments = self.config.get("test_environments", {})
        if env_name not in environments:
            logger.warning(f"环境 {env_name} 不存在，使用默认本地环境")
            env_name = "local"
        return environments.get(env_name, {})
    
    def _setup_monitoring(self, env_config: Dict[str, Any]):
        """设置性能监控"""
        monitoring_config = self.config.get("monitoring", {})
        
        # 系统监控
        if monitoring_config.get("system_monitor", {}).get("enabled", True):
            interval = monitoring_config.get("system_monitor", {}).get("interval", 1.0)
            self.system_monitor = SystemMonitor(interval=interval)
            logger.info("系统监控已设置")
        
        # Redis监控
        if monitoring_config.get("redis_monitor", {}).get("enabled", True):
            redis_config = env_config.get("redis", {})
            interval = monitoring_config.get("redis_monitor", {}).get("interval", 5.0)
            self.redis_monitor = RedisMonitor(
                host=redis_config.get("host", "127.0.0.1"),
                port=redis_config.get("port", 6379),
                request_stream_key=redis_config.get("request_stream_key", "device_raw_messages"),
                response_queue_key=redis_config.get("response_queue_key", "device_responses"),
                interval=interval
            )
            logger.info("Redis监控已设置")
        
        # 数据库监控
        if monitoring_config.get("database_monitor", {}).get("enabled", True):
            db_config = env_config.get("database", {})
            interval = monitoring_config.get("database_monitor", {}).get("interval", 10.0)
            self.database_monitor = DatabaseMonitor(
                host=db_config.get("host", "127.0.0.1"),
                port=db_config.get("port", 3306),
                user=db_config.get("user", "root"),
                password=db_config.get("password", "password"),
                database=db_config.get("database", "rms"),
                interval=interval
            )
            logger.info("数据库监控已设置")
        
        # 应用程序监控
        if monitoring_config.get("application_monitor", {}).get("enabled", True):
            interval = monitoring_config.get("application_monitor", {}).get("interval", 2.0)
            self.application_monitor = ApplicationMonitor(interval=interval)
            logger.info("应用程序监控已设置")
    
    def start_monitoring(self):
        """启动所有监控"""
        if self.system_monitor:
            self.system_monitor.start()
            logger.info("系统监控已启动")
        
        if self.redis_monitor:
            self.redis_monitor.start()
            logger.info("Redis监控已启动")
        
        if self.database_monitor:
            self.database_monitor.start()
            logger.info("数据库监控已启动")
        
        if self.application_monitor:
            self.application_monitor.start()
            logger.info("应用程序监控已启动")
    
    def stop_monitoring(self):
        """停止所有监控"""
        if self.system_monitor:
            self.system_monitor.stop()
            logger.info("系统监控已停止")
        
        if self.redis_monitor:
            self.redis_monitor.stop()
            logger.info("Redis监控已停止")
        
        if self.database_monitor:
            self.database_monitor.stop()
            logger.info("数据库监控已停止")
        
        if self.application_monitor:
            self.application_monitor.stop()
            logger.info("应用程序监控已停止")
    
    def run_smoke_test(self, env_config: Dict[str, Any]) -> TestResult:
        """运行烟雾测试"""
        logger.info("开始运行烟雾测试")
        
        scenario_config = self.config["test_scenarios"]["smoke_test"]["config"]
        tcp_gateway_config = env_config.get("tcp_gateway", {})
        
        test_config = TestConfig(
            host=tcp_gateway_config.get("host", "127.0.0.1"),
            port=tcp_gateway_config.get("ports", {}).get("dp_protocol_v1", 8081),
            concurrent_devices=scenario_config.get("concurrent_devices", 1),
            test_duration=scenario_config.get("test_duration", 30),
            message_interval=scenario_config.get("message_interval", 5.0),
            ramp_up_time=scenario_config.get("ramp_up_time", 0),
            message_weights=scenario_config.get("message_weights", {})
        )
        
        load_tester = LoadTester(test_config)
        result = load_tester.run_load_test()
        result.test_name = "Smoke Test"
        
        return result
    
    def run_load_tests(self, env_config: Dict[str, Any]) -> List[TestResult]:
        """运行负载测试"""
        logger.info("开始运行负载测试")
        
        results = []
        tcp_gateway_config = env_config.get("tcp_gateway", {})
        
        for test_name, test_info in self.config["test_scenarios"].items():
            if not test_info.get("enabled", False):
                logger.info(f"跳过未启用的测试: {test_name}")
                continue
            
            if test_name in ["smoke_test", "stress_test", "concurrent_connection_test"]:
                continue  # 这些测试在其他方法中处理
            
            logger.info(f"运行负载测试: {test_name}")
            scenario_config = test_info["config"]
            
            test_config = TestConfig(
                host=tcp_gateway_config.get("host", "127.0.0.1"),
                port=tcp_gateway_config.get("ports", {}).get("dp_protocol_v1", 8081),
                concurrent_devices=scenario_config.get("concurrent_devices", 10),
                test_duration=scenario_config.get("test_duration", 300),
                message_interval=scenario_config.get("message_interval", 1.0),
                ramp_up_time=scenario_config.get("ramp_up_time", 30),
                message_weights=scenario_config.get("message_weights", {})
            )
            
            load_tester = LoadTester(test_config)
            result = load_tester.run_load_test()
            result.test_name = test_info.get("description", test_name)
            results.append(result)
            
            # 测试间休息
            time.sleep(10)
        
        return results
    
    def run_stress_test(self, env_config: Dict[str, Any]) -> List[TestResult]:
        """运行压力测试"""
        if not self.config["test_scenarios"]["stress_test"].get("enabled", False):
            logger.info("压力测试未启用，跳过")
            return []
        
        logger.info("开始运行压力测试")
        
        scenario_config = self.config["test_scenarios"]["stress_test"]["config"]
        tcp_gateway_config = env_config.get("tcp_gateway", {})
        
        test_config = TestConfig(
            host=tcp_gateway_config.get("host", "127.0.0.1"),
            port=tcp_gateway_config.get("ports", {}).get("dp_protocol_v1", 8081),
            message_interval=scenario_config.get("message_interval", 1.0),
            max_response_time=scenario_config.get("max_response_time", 1.0),
            min_success_rate=scenario_config.get("min_success_rate", 0.95)
        )
        
        stress_tester = StressTester(test_config)
        results = stress_tester.run_stress_test(
            start_devices=scenario_config.get("start_devices", 1),
            max_devices=scenario_config.get("max_devices", 100),
            step_size=scenario_config.get("step_size", 10),
            step_duration=scenario_config.get("step_duration", 120)
        )
        
        return results
    
    def run_concurrent_tests(self, env_config: Dict[str, Any]) -> List[TestResult]:
        """运行并发连接测试"""
        if not self.config["test_scenarios"]["concurrent_connection_test"].get("enabled", False):
            logger.info("并发连接测试未启用，跳过")
            return []
        
        logger.info("开始运行并发连接测试")
        
        scenario_config = self.config["test_scenarios"]["concurrent_connection_test"]["config"]
        tcp_gateway_config = env_config.get("tcp_gateway", {})
        
        concurrent_config = ConcurrentTestConfig(
            host=tcp_gateway_config.get("host", "127.0.0.1"),
            port=tcp_gateway_config.get("ports", {}).get("dp_protocol_v1", 8081),
            max_concurrent_connections=scenario_config.get("max_concurrent_connections", 500),
            connection_ramp_rate=scenario_config.get("connection_ramp_rate", 10.0),
            hold_time=scenario_config.get("hold_time", 300),
            messages_per_connection=scenario_config.get("messages_per_connection", 5),
            message_send_rate=scenario_config.get("message_send_rate", 1.0),
            connection_pattern=scenario_config.get("connection_pattern", "burst"),
            test_scenarios=scenario_config.get("test_scenarios", ["connect_only", "connect_and_send"])
        )
        
        concurrent_tester = ConcurrentTester(concurrent_config)
        results = concurrent_tester.run_all_scenarios()
        
        return results
    
    def check_performance_thresholds(self, results: List[TestResult]) -> Dict[str, bool]:
        """检查性能阈值"""
        thresholds = self.config.get("performance_thresholds", {})
        threshold_results = {}
        
        for result in results:
            test_name = result.test_name
            threshold_results[test_name] = {}
            
            # 检查连接成功率
            if result.connection_success_rate < thresholds.get("connection_success_rate", 0.95):
                threshold_results[test_name]["connection_success_rate"] = False
                logger.warning(f"{test_name}: 连接成功率 {result.connection_success_rate:.2%} 低于阈值")
            else:
                threshold_results[test_name]["connection_success_rate"] = True
            
            # 检查消息成功率
            if result.message_success_rate < thresholds.get("message_success_rate", 0.98):
                threshold_results[test_name]["message_success_rate"] = False
                logger.warning(f"{test_name}: 消息成功率 {result.message_success_rate:.2%} 低于阈值")
            else:
                threshold_results[test_name]["message_success_rate"] = True
            
            # 检查响应时间
            if result.avg_response_time > thresholds.get("max_avg_response_time", 0.1):
                threshold_results[test_name]["avg_response_time"] = False
                logger.warning(f"{test_name}: 平均响应时间 {result.avg_response_time:.3f}s 超过阈值")
            else:
                threshold_results[test_name]["avg_response_time"] = True
        
        return threshold_results
    
    def generate_reports(self, env_name: str):
        """生成测试报告"""
        logger.info("开始生成测试报告")
        
        reporting_config = self.config.get("reporting", {})
        output_dir = reporting_config.get("output_directory", "performance_reports")
        
        # 创建报告生成器
        report_generator = PerformanceReportGenerator(output_dir)
        
        # 收集监控数据
        system_metrics = self.system_monitor.get_metrics() if self.system_monitor else []
        redis_metrics = self.redis_monitor.get_metrics() if self.redis_monitor else []
        db_metrics = self.database_monitor.get_metrics() if self.database_monitor else []
        app_metrics = self.application_monitor.get_metrics() if self.application_monitor else []
        
        # 转换测试结果为字典格式
        test_results_dict = [result.to_dict() for result in self.test_results]
        
        # 生成综合报告
        report_file = report_generator.generate_comprehensive_report(
            test_results_dict,
            system_metrics,
            redis_metrics,
            db_metrics,
            app_metrics
        )
        
        logger.info(f"测试报告已生成: {report_file}")
        return report_file
    
    def run_single_test(self, test_name: str, env_name: str = "local") -> bool:
        """运行单个测试"""
        logger.info(f"运行单个测试: {test_name} (环境: {env_name})")
        
        env_config = self._get_environment_config(env_name)
        self._setup_monitoring(env_config)
        
        try:
            self.start_monitoring()
            self.start_time = time.time()
            
            if test_name == "smoke_test":
                result = self.run_smoke_test(env_config)
                self.test_results = [result]
            elif test_name == "stress_test":
                results = self.run_stress_test(env_config)
                self.test_results = results
            elif test_name == "concurrent_test":
                results = self.run_concurrent_tests(env_config)
                self.test_results = results
            else:
                logger.error(f"未知的测试类型: {test_name}")
                return False
            
            self.end_time = time.time()
            
            # 检查性能阈值
            threshold_results = self.check_performance_thresholds(self.test_results)
            
            # 生成报告
            self.generate_reports(env_name)
            
            logger.info(f"测试 {test_name} 完成")
            return True
            
        except Exception as e:
            logger.error(f"测试 {test_name} 执行失败: {e}")
            return False
        finally:
            self.stop_monitoring()
    
    def run_full_test_suite(self, env_name: str = "local") -> bool:
        """运行完整测试套件"""
        logger.info(f"开始运行完整测试套件 (环境: {env_name})")
        
        env_config = self._get_environment_config(env_name)
        self._setup_monitoring(env_config)
        
        try:
            self.start_monitoring()
            self.start_time = time.time()
            self.test_results = []
            
            # 1. 烟雾测试
            if self.config["test_scenarios"]["smoke_test"].get("enabled", True):
                smoke_result = self.run_smoke_test(env_config)
                self.test_results.append(smoke_result)
                
                # 如果烟雾测试失败，停止后续测试
                if smoke_result.connection_success_rate < 0.5:
                    logger.error("烟雾测试失败严重，停止后续测试")
                    return False
            
            # 2. 负载测试
            load_results = self.run_load_tests(env_config)
            self.test_results.extend(load_results)
            
            # 3. 压力测试
            stress_results = self.run_stress_test(env_config)
            self.test_results.extend(stress_results)
            
            # 4. 并发连接测试
            concurrent_results = self.run_concurrent_tests(env_config)
            self.test_results.extend(concurrent_results)
            
            self.end_time = time.time()
            
            # 检查性能阈值
            threshold_results = self.check_performance_thresholds(self.test_results)
            
            # 生成最终报告
            self.generate_reports(env_name)
            
            logger.info("完整测试套件执行完成")
            return True
            
        except Exception as e:
            logger.error(f"测试套件执行失败: {e}")
            return False
        finally:
            self.stop_monitoring()
    
    def print_summary(self):
        """打印测试摘要"""
        if not self.test_results:
            logger.info("无测试结果")
            return
        
        print("\n" + "="*80)
        print("测试摘要")
        print("="*80)
        
        total_duration = self.end_time - self.start_time if self.start_time and self.end_time else 0
        print(f"总测试时间: {total_duration:.1f} 秒")
        print(f"测试场景数: {len(self.test_results)}")
        
        print("\n详细结果:")
        for result in self.test_results:
            print(f"\n{result.test_name}:")
            print(f"  设备数: {result.total_devices}")
            print(f"  连接成功率: {result.connection_success_rate:.2%}")
            print(f"  消息成功率: {result.message_success_rate:.2%}")
            print(f"  QPS: {result.messages_per_second:.1f}")
            print(f"  平均响应时间: {result.avg_response_time*1000:.1f}ms")
            print(f"  P95响应时间: {result.p95_response_time*1000:.1f}ms")
        
        print("\n" + "="*80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="金融设备通信系统性能测试")
    parser.add_argument("-c", "--config", default="test_config.json", help="配置文件路径")
    parser.add_argument("-e", "--env", default="local", choices=["local", "vm", "staging"], 
                       help="测试环境: local(本地), vm(虚拟机192.168.12.118), staging(测试环境)")
    parser.add_argument("-t", "--test", help="运行单个测试 (smoke_test, stress_test, concurrent_test)")
    parser.add_argument("--full", action="store_true", help="运行完整测试套件")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    parser.add_argument("--log-file", default="performance_test.log", help="日志文件")
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.log_level, args.log_file)
    
    try:
        # 创建测试运行器
        runner = TestRunner(args.config)
        
        success = False
        if args.test:
            # 运行单个测试
            success = runner.run_single_test(args.test, args.env)
        elif args.full:
            # 运行完整测试套件
            success = runner.run_full_test_suite(args.env)
        else:
            # 默认运行烟雾测试
            success = runner.run_single_test("smoke_test", args.env)
        
        # 打印摘要
        runner.print_summary()
        
        if success:
            logger.info("所有测试执行完成")
            sys.exit(0)
        else:
            logger.error("测试执行失败")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
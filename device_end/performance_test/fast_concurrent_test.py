#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速并发连接测试脚本
专门用于测试大量设备的并发连接性能
"""

import argparse
import time
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from enhanced_device_simulator import DeviceSimulatorManager, DeviceConfig, ConnectionConfig, EnhancedDeviceSimulator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('FastConcurrentTest')


class FastConcurrentTester:
    """快速并发测试器"""
    
    def __init__(self, config_file: str = "test_config.json", environment: str = "local"):
        self.manager = DeviceSimulatorManager(config_file, environment)
        self.results_lock = threading.Lock()
        
    def run_concurrent_connection_test(self, device_count: int = 1000, 
                                     max_concurrent: int = 100,
                                     device_prefix: str = "FAST_TEST",
                                     connection_timeout: int = 10) -> Dict:
        """运行并发连接测试"""
        
        print("=" * 80)
        print("🚀 快速并发连接测试")
        print("=" * 80)
        print(f"设备数量: {device_count}")
        print(f"并发连接数: {max_concurrent}")
        print(f"设备前缀: {device_prefix}")
        print(f"连接超时: {connection_timeout}秒")
        print("-" * 80)
        
        # 加载或生成测试设备
        devices = self.manager.load_test_devices(device_prefix, device_count)
        
        if len(devices) < device_count:
            print(f"⚠️  数据库中只有 {len(devices)} 个设备，少于请求的 {device_count} 个")
            print(f"建议运行: python device_batch_inserter.py --count {device_count} --prefix {device_prefix}")
            if len(devices) == 0:
                return self._empty_result()
        
        print(f"✅ 加载了 {len(devices)} 个测试设备")
        
        # 更新连接配置以优化性能
        tcp_config = self.manager.config['tcp_gateway']
        connection_config = ConnectionConfig(
            host=tcp_config['host'],
            port=tcp_config['ports']['dp_protocol_v1'],
            timeout=connection_timeout,  # 使用较短的超时
            reconnect_interval=1,
            max_reconnect_attempts=1
        )
        
        # 创建仿真器
        simulators = []
        for device_config in devices:
            simulator = EnhancedDeviceSimulator(
                device_config, 
                connection_config, 
                self.manager.device_repository
            )
            simulators.append(simulator)
        
        # 执行并发连接测试
        start_time = time.time()
        results = self._execute_concurrent_test(simulators, max_concurrent)
        total_time = time.time() - start_time
        
        # 生成测试报告
        report = self._generate_report(results, total_time, device_count, max_concurrent)
        
        # 清理连接
        self._cleanup_connections(simulators)
        
        return report
    
    def _execute_concurrent_test(self, simulators: List[EnhancedDeviceSimulator], 
                                max_concurrent: int) -> Dict:
        """执行并发连接测试"""
        
        results = {
            'total': len(simulators),
            'connected': 0,
            'registered': 0,
            'authenticated': 0,
            'failed': 0,
            'errors': [],
            'timing_details': []
        }
        
        def process_single_device(simulator, index):
            """处理单个设备的完整流程"""
            device_id = simulator.device_config.device_id
            start_time = time.time()
            
            timing = {
                'device_id': device_id,
                'start_time': start_time,
                'connect_time': 0,
                'register_time': 0,
                'auth_time': 0,
                'total_time': 0,
                'success': False,
                'error': None
            }
            
            try:
                # 1. 建立连接
                connect_start = time.time()
                if simulator.connect():
                    timing['connect_time'] = time.time() - connect_start
                    
                    # 2. 执行注册
                    register_start = time.time()
                    if simulator.perform_registration():
                        timing['register_time'] = time.time() - register_start
                        
                        # 3. 执行鉴权
                        auth_start = time.time()
                        if simulator.perform_authentication():
                            timing['auth_time'] = time.time() - auth_start
                            timing['success'] = True
                            
                            if (index + 1) % 100 == 0:  # 每100个设备打印一次进度
                                logger.info(f"✅ 已完成 {index + 1} 个设备的连接")
                        else:
                            timing['error'] = "鉴权失败"
                    else:
                        timing['error'] = "注册失败"
                else:
                    timing['error'] = "连接失败"
                    
            except Exception as e:
                timing['error'] = f"异常: {str(e)}"
            
            timing['total_time'] = time.time() - start_time
            return timing
        
        print(f"🔄 开始并发连接测试...")
        
        # 使用线程池执行并发测试
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # 提交所有任务
            futures = []
            for i, simulator in enumerate(simulators):
                future = executor.submit(process_single_device, simulator, i)
                futures.append(future)
            
            # 收集结果
            completed = 0
            for future in as_completed(futures, timeout=300):  # 5分钟总超时
                try:
                    timing = future.result()
                    
                    with self.results_lock:
                        results['timing_details'].append(timing)
                        
                        if timing['success']:
                            results['connected'] += 1
                            results['registered'] += 1
                            results['authenticated'] += 1
                        else:
                            results['failed'] += 1
                            if timing['error']:
                                results['errors'].append(f"{timing['device_id']}: {timing['error']}")
                        
                        completed += 1
                        
                        # 显示进度
                        if completed % 50 == 0 or completed == len(simulators):
                            progress = completed / len(simulators) * 100
                            print(f"📊 进度: {completed}/{len(simulators)} ({progress:.1f}%)")
                
                except Exception as e:
                    with self.results_lock:
                        results['failed'] += 1
                        results['errors'].append(f"处理异常: {str(e)}")
                    logger.error(f"处理设备时发生异常: {e}")
        
        return results
    
    def _generate_report(self, results: Dict, total_time: float, 
                        device_count: int, max_concurrent: int) -> Dict:
        """生成测试报告"""
        
        successful_timings = [t for t in results['timing_details'] if t['success']]
        
        if successful_timings:
            avg_connect_time = sum(t['connect_time'] for t in successful_timings) / len(successful_timings)
            avg_register_time = sum(t['register_time'] for t in successful_timings) / len(successful_timings)
            avg_auth_time = sum(t['auth_time'] for t in successful_timings) / len(successful_timings)
            avg_total_time = sum(t['total_time'] for t in successful_timings) / len(successful_timings)
            
            max_time = max(t['total_time'] for t in successful_timings)
            min_time = min(t['total_time'] for t in successful_timings)
        else:
            avg_connect_time = avg_register_time = avg_auth_time = avg_total_time = 0
            max_time = min_time = 0
        
        success_rate = results['authenticated'] / results['total'] * 100
        connections_per_second = results['total'] / total_time
        
        report = {
            'test_summary': {
                'total_devices': results['total'],
                'successful_connections': results['authenticated'],
                'failed_connections': results['failed'],
                'success_rate': success_rate,
                'total_test_time': total_time,
                'connections_per_second': connections_per_second,
                'max_concurrent': max_concurrent
            },
            'timing_statistics': {
                'avg_connect_time': avg_connect_time,
                'avg_register_time': avg_register_time,
                'avg_auth_time': avg_auth_time,
                'avg_total_time': avg_total_time,
                'max_time': max_time,
                'min_time': min_time
            },
            'error_summary': {
                'total_errors': len(results['errors']),
                'error_samples': results['errors'][:10]  # 显示前10个错误
            }
        }
        
        # 打印报告
        print("\n" + "=" * 80)
        print("📊 快速并发连接测试报告")
        print("=" * 80)
        print(f"✅ 测试总结:")
        print(f"   总设备数: {report['test_summary']['total_devices']}")
        print(f"   成功连接: {report['test_summary']['successful_connections']}")
        print(f"   失败连接: {report['test_summary']['failed_connections']}")
        print(f"   成功率: {report['test_summary']['success_rate']:.2f}%")
        print(f"   总测试时间: {report['test_summary']['total_test_time']:.2f}秒")
        print(f"   连接速度: {report['test_summary']['connections_per_second']:.2f} 设备/秒")
        print(f"   最大并发数: {report['test_summary']['max_concurrent']}")
        
        print(f"\n⏱️  时间统计:")
        print(f"   平均连接时间: {report['timing_statistics']['avg_connect_time']:.3f}秒")
        print(f"   平均注册时间: {report['timing_statistics']['avg_register_time']:.3f}秒")
        print(f"   平均鉴权时间: {report['timing_statistics']['avg_auth_time']:.3f}秒")
        print(f"   平均总时间: {report['timing_statistics']['avg_total_time']:.3f}秒")
        print(f"   最长时间: {report['timing_statistics']['max_time']:.3f}秒")
        print(f"   最短时间: {report['timing_statistics']['min_time']:.3f}秒")
        
        if report['error_summary']['total_errors'] > 0:
            print(f"\n❌ 错误汇总:")
            print(f"   总错误数: {report['error_summary']['total_errors']}")
            print(f"   错误示例:")
            for error in report['error_summary']['error_samples']:
                print(f"     - {error}")
        
        print("=" * 80)
        
        # 保存详细报告
        self._save_detailed_report(report, results)
        
        return report
    
    def _save_detailed_report(self, report: Dict, results: Dict):
        """保存详细报告到文件"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_file = f"performance_reports/fast_concurrent_test_{timestamp}.json"
            
            detailed_report = {
                'summary': report,
                'detailed_timings': results['timing_details'],
                'all_errors': results['errors']
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(detailed_report, f, indent=2, ensure_ascii=False)
            
            print(f"💾 详细报告已保存: {report_file}")
            
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
    
    def _cleanup_connections(self, simulators: List[EnhancedDeviceSimulator]):
        """清理所有连接"""
        print("🔄 清理连接中...")
        for simulator in simulators:
            try:
                simulator.disconnect()
            except:
                pass
        print("✅ 连接清理完成")
    
    def _empty_result(self) -> Dict:
        """返回空结果"""
        return {
            'test_summary': {
                'total_devices': 0,
                'successful_connections': 0,
                'failed_connections': 0,
                'success_rate': 0,
                'total_test_time': 0,
                'connections_per_second': 0,
                'max_concurrent': 0
            },
            'timing_statistics': {
                'avg_connect_time': 0,
                'avg_register_time': 0,
                'avg_auth_time': 0,
                'avg_total_time': 0,
                'max_time': 0,
                'min_time': 0
            },
            'error_summary': {
                'total_errors': 1,
                'error_samples': ['没有找到测试设备']
            }
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='快速并发连接测试器')
    parser.add_argument('--config', default='test_config.json', help='配置文件路径')
    parser.add_argument('--environment', default='local', help='测试环境')
    parser.add_argument('--devices', type=int, default=1000, help='测试设备数量')
    parser.add_argument('--concurrent', type=int, default=100, help='最大并发连接数')
    parser.add_argument('--prefix', default='FAST_TEST', help='设备ID前缀')
    parser.add_argument('--timeout', type=int, default=10, help='连接超时时间(秒)')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.devices <= 0:
        print("❌ 设备数量必须大于0")
        return
    
    if args.concurrent <= 0 or args.concurrent > 500:
        print("❌ 并发数必须在1-500之间")
        return
    
    try:
        # 创建测试器
        tester = FastConcurrentTester(args.config, args.environment)
        
        # 运行测试
        result = tester.run_concurrent_connection_test(
            device_count=args.devices,
            max_concurrent=args.concurrent,
            device_prefix=args.prefix,
            connection_timeout=args.timeout
        )
        
        # 显示简要结果
        if result['test_summary']['total_devices'] > 0:
            success_rate = result['test_summary']['success_rate']
            if success_rate >= 95:
                print(f"\n🎉 测试结果优秀！成功率 {success_rate:.1f}%")
            elif success_rate >= 80:
                print(f"\n👍 测试结果良好！成功率 {success_rate:.1f}%")
            else:
                print(f"\n⚠️  测试结果需要改进，成功率 {success_rate:.1f}%")
        
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        logger.exception("测试执行异常")


if __name__ == "__main__":
    main()
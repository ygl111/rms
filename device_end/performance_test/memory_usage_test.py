#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存占用测试脚本
专门测试1000台设备8小时连续发送点钞信息的内存占用情况
模拟场景：每台设备平均发送200张钞票的点钞报告
"""

import argparse
import time
import threading
import random
import logging
import psutil
import os
import sys
import gc
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from enhanced_device_simulator import EnhancedDeviceSimulator, DeviceSimulatorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('MemoryUsageTest')


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, interval: int = 60):
        self.interval = interval
        self.running = False
        self.memory_history = []
        self.process = psutil.Process(os.getpid())
        
    def start_monitoring(self):
        """开始内存监控"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"📊 内存监控已启动，每 {self.interval} 秒记录一次")
    
    def stop_monitoring(self):
        """停止内存监控"""
        self.running = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                # 获取进程内存信息
                memory_info = self.process.memory_info()
                memory_percent = self.process.memory_percent()
                
                # 获取系统内存信息
                virtual_memory = psutil.virtual_memory()
                
                record = {
                    'timestamp': time.time(),
                    'datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'rss_mb': memory_info.rss / 1024 / 1024,  # 物理内存 MB
                    'vms_mb': memory_info.vms / 1024 / 1024,  # 虚拟内存 MB
                    'memory_percent': memory_percent,
                    'system_memory_used_percent': virtual_memory.percent,
                    'system_memory_available_mb': virtual_memory.available / 1024 / 1024
                }
                
                self.memory_history.append(record)
                
                # 打印内存状态
                logger.info(f"🧠 内存状态: RSS={record['rss_mb']:.1f}MB, "
                          f"VMS={record['vms_mb']:.1f}MB, "
                          f"占用={record['memory_percent']:.1f}%, "
                          f"系统={record['system_memory_used_percent']:.1f}%")
                
                # 如果内存使用过高，发出警告
                if record['rss_mb'] > 1000:
                    logger.warning(f"⚠️ 内存使用较高: {record['rss_mb']:.1f}MB")
                if record['rss_mb'] > 2000:
                    logger.error(f"🚨 内存使用过高: {record['rss_mb']:.1f}MB，可能需要优化")
                
                # 限制历史记录数量，避免内存泄漏
                if len(self.memory_history) > 500:
                    self.memory_history = self.memory_history[-400:]
                
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"内存监控异常: {e}")
                time.sleep(self.interval)
    
    def get_memory_stats(self):
        """获取内存统计信息"""
        if not self.memory_history:
            return {}
        
        rss_values = [r['rss_mb'] for r in self.memory_history]
        vms_values = [r['vms_mb'] for r in self.memory_history]
        
        return {
            'initial_rss_mb': rss_values[0],
            'final_rss_mb': rss_values[-1],
            'peak_rss_mb': max(rss_values),
            'avg_rss_mb': sum(rss_values) / len(rss_values),
            'initial_vms_mb': vms_values[0],
            'final_vms_mb': vms_values[-1],
            'peak_vms_mb': max(vms_values),
            'avg_vms_mb': sum(vms_values) / len(vms_values),
            'memory_growth_mb': rss_values[-1] - rss_values[0],
            'total_records': len(self.memory_history)
        }


class MemoryUsageTestRunner:
    """内存占用测试运行器"""
    
    def __init__(self, config_file: str = "test_config.json"):
        self.config_file = config_file
        self.manager = DeviceSimulatorManager(config_file)
        self.running = False
        self.memory_monitor = MemoryMonitor(interval=60)  # 每分钟记录一次内存
        
    def run_banknote_memory_test(self, device_count: int = 1000, 
                                test_duration: int = 28800,  # 8小时 = 28800秒
                                banknotes_per_device: int = 200,
                                device_prefix: str = "MEM_TEST"):
        """
        点钞内存占用测试
        模拟1000台设备8小时连续发送点钞信息，每台设备平均200张钞票
        """
        logger.info("="*80)
        logger.info(f"💰 开始点钞内存占用测试")
        logger.info(f"🎯 测试参数:")
        logger.info(f"   设备数量: {device_count} 台")
        logger.info(f"   测试时长: {test_duration} 秒 ({test_duration//3600:.1f} 小时)")
        logger.info(f"   每台设备钞票数: {banknotes_per_device} 张")
        logger.info(f"   预期总点钞报告: {device_count * banknotes_per_device} 条")
        logger.info("="*80)
        
        # 开始内存监控
        self.memory_monitor.start_monitoring()
        
        # 记录初始内存状态
        initial_memory = psutil.Process(os.getpid()).memory_info()
        logger.info(f"📊 初始内存状态: RSS={initial_memory.rss/1024/1024:.1f}MB, "
                   f"VMS={initial_memory.vms/1024/1024:.1f}MB")
        
        try:
            # 加载测试设备
            logger.info(f"🔧 正在生成 {device_count} 台测试设备...")
            device_configs = self.manager.load_test_devices(device_prefix, device_count)
            
            if len(device_configs) < device_count:
                logger.warning(f"只生成了 {len(device_configs)} 台设备，少于请求的 {device_count} 台")
                device_count = len(device_configs)
            
            # 创建设备模拟器
            self.manager.create_simulators(device_configs)
            logger.info(f"✅ 已创建 {len(self.manager.simulators)} 台设备模拟器")
            
            # 检查创建设备后的内存使用
            after_create_memory = psutil.Process(os.getpid()).memory_info()
            logger.info(f"📊 创建设备后内存: RSS={after_create_memory.rss/1024/1024:.1f}MB "
                       f"(增长 {(after_create_memory.rss-initial_memory.rss)/1024/1024:.1f}MB)")
            
            # 批量连接设备（分批连接避免一次性压力过大）
            logger.info(f"📡 开始分批连接设备...")
            batch_size = 50  # 每批连接50台设备
            connected_count = 0
            
            for i in range(0, len(self.manager.simulators), batch_size):
                batch = self.manager.simulators[i:i+batch_size]
                batch_start = time.time()
                
                # 并发连接这批设备
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = []
                    for sim in batch:
                        future = executor.submit(self._connect_and_authenticate, sim)
                        futures.append(future)
                    
                    # 等待这批设备连接完成
                    for future in futures:
                        try:
                            if future.result():
                                connected_count += 1
                        except Exception as e:
                            logger.error(f"设备连接失败: {e}")
                
                batch_time = time.time() - batch_start
                logger.info(f"   批次 {i//batch_size + 1}: 连接 {len(batch)} 台设备，"
                           f"成功 {len([f for f in futures if f.result()])}/{len(batch)}，"
                           f"用时 {batch_time:.1f}s")
                
                # 批次间短暂休息
                time.sleep(1)
            
            logger.info(f"✅ 设备连接完成: {connected_count}/{device_count} 台成功连接")
            
            # 检查连接后的内存使用
            after_connect_memory = psutil.Process(os.getpid()).memory_info()
            logger.info(f"📊 连接设备后内存: RSS={after_connect_memory.rss/1024/1024:.1f}MB "
                       f"(增长 {(after_connect_memory.rss-after_create_memory.rss)/1024/1024:.1f}MB)")
            
            if connected_count == 0:
                logger.error("❌ 没有设备成功连接，测试终止")
                return False
            
            # 开始点钞报告测试
            logger.info(f"💰 开始发送点钞报告...")
            
            # 计算发送间隔（8小时内平均发送200张钞票）
            send_interval = test_duration / banknotes_per_device  # 每张钞票的发送间隔
            logger.info(f"📅 发送策略: 每台设备每 {send_interval:.1f} 秒发送一张钞票报告")
            
            self.running = True
            start_time = time.time()
            
            # 统计信息
            total_sent = 0
            total_success = 0
            total_failed = 0
            
            # 创建发送任务队列
            send_queue = []
            for sim in self.manager.simulators:
                if sim.connected:
                    # 为每台设备计划发送时间
                    for i in range(banknotes_per_device):
                        send_time = start_time + i * send_interval + random.uniform(0, send_interval * 0.1)
                        send_queue.append((send_time, sim, i + 1))
            
            # 按时间排序
            send_queue.sort(key=lambda x: x[0])
            logger.info(f"📋 已安排 {len(send_queue)} 条点钞报告发送任务")
            
            # 发送循环
            queue_index = 0
            last_progress_time = start_time
            
            while self.running and (time.time() - start_time) < test_duration and queue_index < len(send_queue):
                current_time = time.time()
                
                # 检查是否有需要发送的消息
                sent_this_round = 0
                while (queue_index < len(send_queue) and 
                       send_queue[queue_index][0] <= current_time and 
                       sent_this_round < 50):  # 每轮最多发送50条，避免突发
                    
                    send_time, sim, banknote_seq = send_queue[queue_index]
                    
                    try:
                        # 发送点钞报告
                        success = sim.send_banknote_report(
                            banknote_count=random.randint(50, 100),  # 随机50-100张钞票
                            amount=random.randint(5000, 50000),      # 随机金额5000-50000分
                            currency='CNY',
                            recv_timeout=10.0
                        )
                        
                        if success:
                            total_success += 1
                        else:
                            total_failed += 1
                        
                        total_sent += 1
                        sent_this_round += 1
                        
                    except Exception as e:
                        logger.debug(f"发送点钞报告失败: {e}")
                        total_failed += 1
                        total_sent += 1
                    
                    queue_index += 1
                
                # 定期报告进度（每10分钟）
                if current_time - last_progress_time >= 600:
                    elapsed_hours = (current_time - start_time) / 3600
                    progress_percent = (queue_index / len(send_queue)) * 100
                    success_rate = (total_success / total_sent * 100) if total_sent > 0 else 0
                    current_qps = total_sent / (current_time - start_time)
                    
                    logger.info(f"📊 测试进展 ({elapsed_hours:.1f}小时):")
                    logger.info(f"   进度: {progress_percent:.1f}% ({queue_index}/{len(send_queue)})")
                    logger.info(f"   发送统计: 成功{total_success}, 失败{total_failed}, 成功率{success_rate:.1f}%")
                    logger.info(f"   发送速度: {current_qps:.1f} 条/秒")
                    
                    last_progress_time = current_time
                    
                    # 手动触发垃圾回收
                    gc.collect()
                
                # 短暂休息，避免CPU占用过高
                time.sleep(0.1)
            
            # 测试完成
            end_time = time.time()
            actual_duration = end_time - start_time
            
            logger.info("="*80)
            logger.info(f"✅ 点钞内存占用测试完成!")
            logger.info(f"⏱️  测试时长: {actual_duration:.1f} 秒 ({actual_duration/3600:.1f} 小时)")
            logger.info(f"📊 发送统计:")
            logger.info(f"   总发送: {total_sent} 条点钞报告")
            logger.info(f"   成功: {total_success} 条 ({total_success/total_sent*100:.1f}%)")
            logger.info(f"   失败: {total_failed} 条 ({total_failed/total_sent*100:.1f}%)")
            logger.info(f"   平均QPS: {total_sent/actual_duration:.1f} 条/秒")
            
            # 获取最终内存状态
            final_memory = psutil.Process(os.getpid()).memory_info()
            memory_stats = self.memory_monitor.get_memory_stats()
            
            logger.info(f"🧠 内存使用分析:")
            logger.info(f"   初始内存: {initial_memory.rss/1024/1024:.1f}MB")
            logger.info(f"   最终内存: {final_memory.rss/1024/1024:.1f}MB")
            logger.info(f"   内存增长: {(final_memory.rss-initial_memory.rss)/1024/1024:.1f}MB")
            
            if memory_stats:
                logger.info(f"   峰值内存: {memory_stats['peak_rss_mb']:.1f}MB")
                logger.info(f"   平均内存: {memory_stats['avg_rss_mb']:.1f}MB")
            
            # 计算每台设备的内存开销
            memory_per_device = (final_memory.rss - initial_memory.rss) / device_count
            logger.info(f"   每台设备内存开销: {memory_per_device/1024:.1f}KB")
            
            # 计算每条消息的内存开销
            if total_sent > 0:
                memory_per_message = (final_memory.rss - initial_memory.rss) / total_sent
                logger.info(f"   每条消息内存开销: {memory_per_message:.0f}字节")
            
            logger.info("="*80)
            
            # 生成详细报告
            self._generate_memory_report(
                device_count, actual_duration, total_sent, total_success, total_failed,
                initial_memory, final_memory, memory_stats
            )
            
            return True
            
        except Exception as e:
            logger.error(f"测试执行异常: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self.running = False
            self.memory_monitor.stop_monitoring()
            
            # 清理资源
            if hasattr(self, 'manager'):
                self.manager.stop_all_simulators()
    
    def _connect_and_authenticate(self, simulator):
        """连接并认证设备"""
        try:
            # 连接
            if not simulator.connect():
                return False
            
            # 等待短暂时间
            time.sleep(0.1)
            
            # 注册
            if not simulator.register():
                return False
                
            # 认证
            if not simulator.authenticate():
                return False
            
            return True
        except Exception as e:
            logger.debug(f"设备 {simulator.device_config.device_id} 连接失败: {e}")
            return False
    
    def _generate_memory_report(self, device_count, duration, total_sent, total_success, 
                               total_failed, initial_memory, final_memory, memory_stats):
        """生成内存使用报告"""
        report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"performance_test/memory_usage_report_{report_time}.html"
        
        # 计算关键指标
        memory_growth = (final_memory.rss - initial_memory.rss) / 1024 / 1024
        memory_per_device = memory_growth / device_count if device_count > 0 else 0
        memory_per_message = (final_memory.rss - initial_memory.rss) / total_sent if total_sent > 0 else 0
        success_rate = (total_success / total_sent * 100) if total_sent > 0 else 0
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>点钞内存占用测试报告</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        .summary {{ background-color: #e8f6ff; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 15px; padding: 15px; background-color: #f9f9f9; 
                  border-radius: 5px; min-width: 180px; text-align: center; }}
        .good {{ color: #27ae60; font-weight: bold; }}
        .warning {{ color: #f39c12; font-weight: bold; }}
        .error {{ color: #e74c3c; font-weight: bold; }}
        .key-metric {{ font-size: 24px; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>💰 点钞内存占用测试报告</h1>
    <p><strong>生成时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="summary">
        <h2>📊 测试摘要</h2>
        <div class="metric">
            <strong>设备数量:</strong><br>
            <span class="key-metric">{device_count}</span> 台
        </div>
        <div class="metric">
            <strong>测试时长:</strong><br>
            <span class="key-metric">{duration/3600:.1f}</span> 小时
        </div>
        <div class="metric">
            <strong>总消息数:</strong><br>
            <span class="key-metric">{total_sent:,}</span> 条
        </div>
        <div class="metric">
            <strong>成功率:</strong><br>
            <span class="key-metric {'good' if success_rate >= 95 else 'warning' if success_rate >= 90 else 'error'}">{success_rate:.1f}%</span>
        </div>
    </div>
    
    <div class="summary">
        <h2>🧠 内存使用分析</h2>
        <div class="metric">
            <strong>内存增长:</strong><br>
            <span class="key-metric {'good' if memory_growth < 500 else 'warning' if memory_growth < 1000 else 'error'}">{memory_growth:.1f}</span> MB
        </div>
        <div class="metric">
            <strong>每台设备开销:</strong><br>
            <span class="key-metric">{memory_per_device*1024:.1f}</span> KB
        </div>
        <div class="metric">
            <strong>每条消息开销:</strong><br>
            <span class="key-metric">{memory_per_message:.0f}</span> 字节
        </div>
        <div class="metric">
            <strong>峰值内存:</strong><br>
            <span class="key-metric">{memory_stats.get('peak_rss_mb', 0):.1f}</span> MB
        </div>
    </div>
    
    <h2>📋 详细数据</h2>
    <table>
        <tr><th>指标项</th><th>数值</th><th>说明</th></tr>
        <tr><td>初始内存 (RSS)</td><td>{initial_memory.rss/1024/1024:.1f} MB</td><td>测试开始时物理内存使用</td></tr>
        <tr><td>最终内存 (RSS)</td><td>{final_memory.rss/1024/1024:.1f} MB</td><td>测试结束时物理内存使用</td></tr>
        <tr><td>内存增长</td><td>{memory_growth:.1f} MB</td><td>测试期间内存净增长</td></tr>
        <tr><td>初始虚拟内存</td><td>{initial_memory.vms/1024/1024:.1f} MB</td><td>测试开始时虚拟内存</td></tr>
        <tr><td>最终虚拟内存</td><td>{final_memory.vms/1024/1024:.1f} MB</td><td>测试结束时虚拟内存</td></tr>
        <tr><td>发送消息总数</td><td>{total_sent:,} 条</td><td>实际发送的点钞报告数量</td></tr>
        <tr><td>成功消息数</td><td>{total_success:,} 条</td><td>发送成功的消息数量</td></tr>
        <tr><td>失败消息数</td><td>{total_failed:,} 条</td><td>发送失败的消息数量</td></tr>
        <tr><td>平均QPS</td><td>{total_sent/duration:.1f} 条/秒</td><td>每秒发送消息数量</td></tr>
    </table>
    
    <h2>💡 分析结论</h2>
    <ul>
"""
        
        # 添加分析结论
        if memory_per_device * 1024 < 50:  # 每台设备小于50KB
            html_content += "<li>✅ 每台设备内存开销很低，系统资源利用合理</li>"
        elif memory_per_device * 1024 < 200:  # 每台设备小于200KB  
            html_content += "<li>⚠️ 每台设备内存开销中等，可接受范围内</li>"
        else:
            html_content += "<li>❌ 每台设备内存开销较高，需要优化</li>"
        
        if memory_per_message < 1024:  # 每条消息小于1KB
            html_content += "<li>✅ 每条消息内存开销很低，协议设计合理</li>"
        elif memory_per_message < 2048:  # 每条消息小于2KB
            html_content += "<li>⚠️ 每条消息内存开销中等，可考虑优化</li>"
        else:
            html_content += "<li>❌ 每条消息内存开销较高，建议优化协议或实现</li>"
        
        if success_rate >= 98:
            html_content += "<li>✅ 消息发送成功率优秀，系统稳定性很好</li>"
        elif success_rate >= 95:
            html_content += "<li>⚠️ 消息发送成功率良好，有小幅提升空间</li>"
        else:
            html_content += "<li>❌ 消息发送成功率较低，需要排查系统问题</li>"
        
        # 预测更大规模的内存使用
        projected_5k = memory_growth * 5
        projected_10k = memory_growth * 10
        
        html_content += f"""
    </ul>
    
    <h2>🔮 规模预测</h2>
    <p>基于当前测试数据，预测更大规模部署的内存需求：</p>
    <ul>
        <li><strong>5000台设备 (8小时):</strong> 约需额外 {projected_5k:.0f} MB 内存</li>
        <li><strong>10000台设备 (8小时):</strong> 约需额外 {projected_10k:.0f} MB 内存</li>
        <li><strong>内存规划建议:</strong> 建议至少预留 {projected_10k*1.5:.0f} MB 内存用于高峰期缓冲</li>
    </ul>
    
    <h2>📈 优化建议</h2>
    <ul>
        <li>定期进行垃圾回收，避免内存碎片积累</li>
        <li>监控长期运行的内存增长趋势，及时发现内存泄漏</li>
        <li>考虑使用对象池技术复用消息对象</li>
        <li>优化数据结构，减少不必要的内存开销</li>
        <li>实现消息批处理，提高内存使用效率</li>
    </ul>
    
    <hr>
    <p><em>此报告由点钞内存占用测试自动生成 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</em></p>
</body>
</html>
        """
        
        # 保存报告
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"📋 详细报告已保存: {report_file}")
        except Exception as e:
            logger.error(f"保存报告失败: {e}")


def main():
    parser = argparse.ArgumentParser(description='点钞内存占用测试')
    parser.add_argument("--devices", type=int, default=1000, help="测试设备数量")
    parser.add_argument("--duration", type=int, default=28800, help="测试持续时间(秒)，默认8小时")  
    parser.add_argument("--banknotes", type=int, default=200, help="每台设备的钞票数量")
    parser.add_argument("--config", type=str, default="test_config.json", help="配置文件路径")
    parser.add_argument("--device-prefix", type=str, default="MEM_TEST", help="设备ID前缀")
    
    args = parser.parse_args()
    
    logger.info("🚀 启动点钞内存占用测试")
    logger.info(f"📋 测试参数: {args.devices}台设备, {args.duration//3600:.1f}小时, 每台{args.banknotes}张钞票")
    
    try:
        runner = MemoryUsageTestRunner(args.config)
        success = runner.run_banknote_memory_test(
            device_count=args.devices,
            test_duration=args.duration, 
            banknotes_per_device=args.banknotes,
            device_prefix=args.device_prefix
        )
        
        if success:
            logger.info("🎉 内存占用测试成功完成！")
        else:
            logger.error("💥 内存占用测试失败！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⛔ 测试被用户中断")
    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
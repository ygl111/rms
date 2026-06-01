#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控和报告生成模块
用于收集系统性能指标并生成详细的测试报告
"""

import psutil
import time
import json
import threading
import csv
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import redis
import mysql.connector
import logging

logger = logging.getLogger('PerformanceMonitor')


@dataclass
class SystemMetrics:
    """系统性能指标"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    tcp_connections: int
    process_count: int


@dataclass
class RedisMetrics:
    """Redis性能指标"""
    timestamp: float
    connected_clients: int
    used_memory_mb: float
    used_memory_peak_mb: float
    total_commands_processed: int
    instantaneous_ops_per_sec: int
    keyspace_hits: int
    keyspace_misses: int
    hit_rate: float
    
    # Stream相关指标
    stream_length: int = 0
    stream_groups: int = 0
    
    # List相关指标
    list_length: int = 0


@dataclass
class DatabaseMetrics:
    """数据库性能指标"""
    timestamp: float
    threads_connected: int
    threads_running: int
    queries_per_second: float
    slow_queries: int
    table_locks_waited: int
    innodb_buffer_pool_hit_rate: float


@dataclass
class ApplicationMetrics:
    """应用程序性能指标"""
    timestamp: float
    tcp_gateway_cpu: float = 0.0
    tcp_gateway_memory_mb: float = 0.0
    cpp_parser_cpu: float = 0.0
    cpp_parser_memory_mb: float = 0.0
    tcp_gateway_connections: int = 0
    cpp_parser_threads: int = 0


class SystemMonitor:
    """系统性能监控器"""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.metrics: List[SystemMetrics] = []
        self.running = False
        self.lock = threading.Lock()
        
        # 初始化网络和磁盘IO计数器
        self._last_disk_io = psutil.disk_io_counters()
        self._last_network_io = psutil.net_io_counters()
        self._last_time = time.time()
    
    def start(self):
        """开始监控"""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=5)
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                metrics = self._collect_system_metrics()
                with self.lock:
                    self.metrics.append(metrics)
                    # 限制数据量，只保留最近的数据
                    if len(self.metrics) > 3600:  # 1小时的数据（1秒间隔）
                        self.metrics = self.metrics[-3600:]
                
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"系统监控异常: {e}")
                time.sleep(self.interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统性能指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent()
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / 1024 / 1024
        memory_available_mb = memory.available / 1024 / 1024
        
        # 磁盘IO
        current_disk_io = psutil.disk_io_counters()
        current_time = time.time()
        time_delta = current_time - self._last_time
        
        if time_delta > 0 and self._last_disk_io:
            disk_read_mb = (current_disk_io.read_bytes - self._last_disk_io.read_bytes) / 1024 / 1024 / time_delta
            disk_write_mb = (current_disk_io.write_bytes - self._last_disk_io.write_bytes) / 1024 / 1024 / time_delta
        else:
            disk_read_mb = disk_write_mb = 0.0
        
        # 网络IO
        current_network_io = psutil.net_io_counters()
        if time_delta > 0 and self._last_network_io:
            network_sent_mb = (current_network_io.bytes_sent - self._last_network_io.bytes_sent) / 1024 / 1024 / time_delta
            network_recv_mb = (current_network_io.bytes_recv - self._last_network_io.bytes_recv) / 1024 / 1024 / time_delta
        else:
            network_sent_mb = network_recv_mb = 0.0
        
        # TCP连接数
        tcp_connections = len([conn for conn in psutil.net_connections() if conn.type == 1])  # SOCK_STREAM
        
        # 进程数
        process_count = len(psutil.pids())
        
        # 更新上次的值
        self._last_disk_io = current_disk_io
        self._last_network_io = current_network_io
        self._last_time = current_time
        
        return SystemMetrics(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            tcp_connections=tcp_connections,
            process_count=process_count
        )
    
    def get_metrics(self) -> List[SystemMetrics]:
        """获取监控数据"""
        with self.lock:
            return self.metrics.copy()


class RedisMonitor:
    """Redis性能监控器"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, 
                 request_stream_key: str = "device_raw_messages",
                 response_queue_key: str = "device_responses",
                 interval: float = 5.0):
        self.host = host
        self.port = port
        self.request_stream_key = request_stream_key
        self.response_queue_key = response_queue_key
        self.interval = interval
        self.metrics: List[RedisMetrics] = []
        self.running = False
        self.lock = threading.Lock()
        
        try:
            self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
            # 测试连接
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}")
            self.redis_client = None
    
    def start(self):
        """开始监控"""
        if not self.redis_client:
            logger.warning("Redis客户端未初始化，跳过Redis监控")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=5)
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                metrics = self._collect_redis_metrics()
                if metrics:
                    with self.lock:
                        self.metrics.append(metrics)
                        # 限制数据量
                        if len(self.metrics) > 720:  # 1小时的数据（5秒间隔）
                            self.metrics = self.metrics[-720:]
                
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Redis监控异常: {e}")
                time.sleep(self.interval)
    
    def _collect_redis_metrics(self) -> Optional[RedisMetrics]:
        """收集Redis性能指标"""
        if not self.redis_client:
            return None
        
        try:
            info = self.redis_client.info()
            
            # 基本指标
            connected_clients = info.get('connected_clients', 0)
            used_memory = info.get('used_memory', 0) / 1024 / 1024  # MB
            used_memory_peak = info.get('used_memory_peak', 0) / 1024 / 1024  # MB
            total_commands_processed = info.get('total_commands_processed', 0)
            instantaneous_ops_per_sec = info.get('instantaneous_ops_per_sec', 0)
            
            # 命中率
            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses) if (keyspace_hits + keyspace_misses) > 0 else 0.0
            
            # Stream长度
            try:
                stream_length = self.redis_client.xlen(self.request_stream_key)
            except:
                stream_length = 0
            
            # List长度
            try:
                list_length = self.redis_client.llen(self.response_queue_key)
            except:
                list_length = 0
            
            # Stream组数
            try:
                stream_groups = len(self.redis_client.xinfo_groups(self.request_stream_key))
            except:
                stream_groups = 0
            
            return RedisMetrics(
                timestamp=time.time(),
                connected_clients=connected_clients,
                used_memory_mb=used_memory,
                used_memory_peak_mb=used_memory_peak,
                total_commands_processed=total_commands_processed,
                instantaneous_ops_per_sec=instantaneous_ops_per_sec,
                keyspace_hits=keyspace_hits,
                keyspace_misses=keyspace_misses,
                hit_rate=hit_rate,
                stream_length=stream_length,
                stream_groups=stream_groups,
                list_length=list_length
            )
        
        except Exception as e:
            logger.error(f"收集Redis指标失败: {e}")
            return None
    
    def get_metrics(self) -> List[RedisMetrics]:
        """获取监控数据"""
        with self.lock:
            return self.metrics.copy()


class DatabaseMonitor:
    """数据库性能监控器"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 3306,
                 user: str = "root", password: str = "password",
                 database: str = "rms", interval: float = 10.0):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.interval = interval
        self.metrics: List[DatabaseMetrics] = []
        self.running = False
        self.lock = threading.Lock()
        
        try:
            self.db_connection = mysql.connector.connect(
                host=host, port=port, user=user, password=password, database=database
            )
        except Exception as e:
            logger.warning(f"MySQL连接失败: {e}")
            self.db_connection = None
    
    def start(self):
        """开始监控"""
        if not self.db_connection:
            logger.warning("数据库连接未初始化，跳过数据库监控")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=5)
        
        if self.db_connection:
            self.db_connection.close()
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                metrics = self._collect_database_metrics()
                if metrics:
                    with self.lock:
                        self.metrics.append(metrics)
                        # 限制数据量
                        if len(self.metrics) > 360:  # 1小时的数据（10秒间隔）
                            self.metrics = self.metrics[-360:]
                
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"数据库监控异常: {e}")
                time.sleep(self.interval)
    
    def _collect_database_metrics(self) -> Optional[DatabaseMetrics]:
        """收集数据库性能指标"""
        if not self.db_connection:
            return None
        
        try:
            cursor = self.db_connection.cursor()
            
            # 获取状态变量
            cursor.execute("SHOW STATUS")
            status_vars = dict(cursor.fetchall())
            
            # 获取全局变量
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Threads_%'")
            thread_vars = dict(cursor.fetchall())
            
            cursor.close()
            
            # 计算指标
            threads_connected = int(thread_vars.get('Threads_connected', 0))
            threads_running = int(thread_vars.get('Threads_running', 0))
            
            queries = int(status_vars.get('Queries', 0))
            uptime = int(status_vars.get('Uptime', 1))
            queries_per_second = queries / uptime if uptime > 0 else 0
            
            slow_queries = int(status_vars.get('Slow_queries', 0))
            table_locks_waited = int(status_vars.get('Table_locks_waited', 0))
            
            # InnoDB缓冲池命中率
            innodb_buffer_pool_reads = int(status_vars.get('Innodb_buffer_pool_reads', 0))
            innodb_buffer_pool_read_requests = int(status_vars.get('Innodb_buffer_pool_read_requests', 0))
            
            if innodb_buffer_pool_read_requests > 0:
                innodb_buffer_pool_hit_rate = 1 - (innodb_buffer_pool_reads / innodb_buffer_pool_read_requests)
            else:
                innodb_buffer_pool_hit_rate = 0.0
            
            return DatabaseMetrics(
                timestamp=time.time(),
                threads_connected=threads_connected,
                threads_running=threads_running,
                queries_per_second=queries_per_second,
                slow_queries=slow_queries,
                table_locks_waited=table_locks_waited,
                innodb_buffer_pool_hit_rate=innodb_buffer_pool_hit_rate
            )
        
        except Exception as e:
            logger.error(f"收集数据库指标失败: {e}")
            return None
    
    def get_metrics(self) -> List[DatabaseMetrics]:
        """获取监控数据"""
        with self.lock:
            return self.metrics.copy()


class ApplicationMonitor:
    """应用程序性能监控器"""
    
    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.metrics: List[ApplicationMetrics] = []
        self.running = False
        self.lock = threading.Lock()
    
    def start(self):
        """开始监控"""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=5)
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                metrics = self._collect_application_metrics()
                if metrics:
                    with self.lock:
                        self.metrics.append(metrics)
                        # 限制数据量
                        if len(self.metrics) > 1800:  # 1小时的数据（2秒间隔）
                            self.metrics = self.metrics[-1800:]
                
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"应用监控异常: {e}")
                time.sleep(self.interval)
    
    def _collect_application_metrics(self) -> Optional[ApplicationMetrics]:
        """收集应用程序性能指标"""
        tcp_gateway_cpu = tcp_gateway_memory = 0.0
        cpp_parser_cpu = cpp_parser_memory = 0.0
        tcp_gateway_connections = cpp_parser_threads = 0
        
        try:
            # 查找TCP Gateway进程
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    proc_info = proc.info
                    if 'gateway' in proc_info['name'].lower():
                        tcp_gateway_cpu = proc_info['cpu_percent'] or 0.0
                        memory_info = proc_info['memory_info']
                        tcp_gateway_memory = memory_info.rss / 1024 / 1024 if memory_info else 0.0
                        # 尝试获取连接数，如果失败就设为0
                        try:
                            proc_obj = psutil.Process(proc_info['pid'])
                            connections = proc_obj.connections()
                            tcp_gateway_connections = len(connections)
                        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                            tcp_gateway_connections = 0
                    elif 'cpp_parser' in proc_info['name'].lower() or 'parser' in proc_info['name'].lower():
                        tcp_gateway_cpu = proc_info['cpu_percent'] or 0.0
                        memory_info = proc_info['memory_info']
                        cpp_parser_memory = memory_info.rss / 1024 / 1024 if memory_info else 0.0
                        # 获取线程数
                        try:
                            cpp_parser_threads = proc.num_threads()
                        except:
                            cpp_parser_threads = 0
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return ApplicationMetrics(
                timestamp=time.time(),
                tcp_gateway_cpu=tcp_gateway_cpu,
                tcp_gateway_memory_mb=tcp_gateway_memory,
                cpp_parser_cpu=cpp_parser_cpu,
                cpp_parser_memory_mb=cpp_parser_memory,
                tcp_gateway_connections=tcp_gateway_connections,
                cpp_parser_threads=cpp_parser_threads
            )
        
        except Exception as e:
            logger.error(f"收集应用指标失败: {e}")
            return None
    
    def get_metrics(self) -> List[ApplicationMetrics]:
        """获取监控数据"""
        with self.lock:
            return self.metrics.copy()


class PerformanceReportGenerator:
    """性能报告生成器"""
    
    def __init__(self, output_dir: str = "performance_reports"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_comprehensive_report(self, test_results: List[Dict], 
                                    system_metrics: List[SystemMetrics],
                                    redis_metrics: List[RedisMetrics] = None,
                                    db_metrics: List[DatabaseMetrics] = None,
                                    app_metrics: List[ApplicationMetrics] = None) -> str:
        """生成综合性能报告"""
        
        report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{self.output_dir}/performance_report_{report_time}.html"
        
        # 生成HTML报告
        html_content = self._generate_html_report(
            test_results, system_metrics, redis_metrics, db_metrics, app_metrics
        )
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 生成CSV数据文件
        self._export_csv_data(test_results, system_metrics, redis_metrics, db_metrics, app_metrics, report_time)
        
        # 生成图表
        self._generate_charts(system_metrics, redis_metrics, db_metrics, app_metrics, report_time)
        
        logger.info(f"性能报告已生成: {report_file}")
        return report_file
    
    def _generate_html_report(self, test_results: List[Dict], 
                             system_metrics: List[SystemMetrics],
                             redis_metrics: List[RedisMetrics] = None,
                             db_metrics: List[DatabaseMetrics] = None,
                             app_metrics: List[ApplicationMetrics] = None) -> str:
        """生成HTML报告"""
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>金融设备通信系统性能测试报告</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #e8f6ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 5px; }}
        .chart {{ margin: 20px 0; text-align: center; }}
        .good {{ color: green; font-weight: bold; }}
        .warning {{ color: orange; font-weight: bold; }}
        .error {{ color: red; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>金融设备通信系统性能测试报告</h1>
    <p><strong>生成时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="summary">
        <h2>测试摘要</h2>
        <div class="metric">
            <strong>测试场景数:</strong> {len(test_results)}
        </div>
        <div class="metric">
            <strong>系统监控数据点:</strong> {len(system_metrics)}
        </div>
        <div class="metric">
            <strong>监控时长:</strong> {self._format_duration(system_metrics)}
        </div>
    </div>
    
    <h2>测试结果详情</h2>
    {self._generate_test_results_table(test_results)}
    
    <h2>系统性能指标</h2>
    {self._generate_system_metrics_summary(system_metrics)}
    
    {self._generate_redis_metrics_section(redis_metrics) if redis_metrics else ""}
    
    {self._generate_database_metrics_section(db_metrics) if db_metrics else ""}
    
    {self._generate_application_metrics_section(app_metrics) if app_metrics else ""}
    
    <h2>性能图表</h2>
    <p>详细的性能图表已保存为单独的PNG文件，请查看同目录下的图表文件。</p>
    
    <h2>建议和结论</h2>
    {self._generate_recommendations(test_results, system_metrics)}
    
</body>
</html>
        """
        
        return html
    
    def _generate_test_results_table(self, test_results: List[Dict]) -> str:
        """生成测试结果表格"""
        if not test_results:
            return "<p>无测试结果数据</p>"
        
        table_html = """
        <table>
            <tr>
                <th>测试名称</th>
                <th>设备数</th>
                <th>连接成功率</th>
                <th>消息成功率</th>
                <th>QPS</th>
                <th>平均响应时间(ms)</th>
                <th>P95响应时间(ms)</th>
                <th>测试时长(s)</th>
            </tr>
        """
        
        for result in test_results:
            connection_success_rate = result.get('connection_success_rate', 0) * 100
            message_success_rate = result.get('message_success_rate', 0) * 100
            qps = result.get('messages_per_second', 0)
            avg_response_time = result.get('avg_response_time', 0) * 1000
            p95_response_time = result.get('p95_response_time', 0) * 1000
            duration = result.get('duration', 0)
            
            # 根据性能指标设置样式
            conn_class = "good" if connection_success_rate >= 95 else "warning" if connection_success_rate >= 90 else "error"
            msg_class = "good" if message_success_rate >= 95 else "warning" if message_success_rate >= 90 else "error"
            
            table_html += f"""
            <tr>
                <td>{result.get('test_name', 'Unknown')}</td>
                <td>{result.get('total_devices', 0)}</td>
                <td class="{conn_class}">{connection_success_rate:.1f}%</td>
                <td class="{msg_class}">{message_success_rate:.1f}%</td>
                <td>{qps:.1f}</td>
                <td>{avg_response_time:.1f}</td>
                <td>{p95_response_time:.1f}</td>
                <td>{duration:.1f}</td>
            </tr>
            """
        
        table_html += "</table>"
        return table_html
    
    def _generate_system_metrics_summary(self, system_metrics: List[SystemMetrics]) -> str:
        """生成系统性能指标摘要"""
        if not system_metrics:
            return "<p>无系统性能数据</p>"
        
        # 计算统计信息
        cpu_values = [m.cpu_percent for m in system_metrics]
        memory_values = [m.memory_percent for m in system_metrics]
        tcp_conn_values = [m.tcp_connections for m in system_metrics]
        
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)
        avg_memory = sum(memory_values) / len(memory_values)
        max_memory = max(memory_values)
        avg_tcp_conns = sum(tcp_conn_values) / len(tcp_conn_values)
        max_tcp_conns = max(tcp_conn_values)
        
        return f"""
        <div class="summary">
            <div class="metric">
                <strong>平均CPU使用率:</strong> {avg_cpu:.1f}%
            </div>
            <div class="metric">
                <strong>峰值CPU使用率:</strong> {max_cpu:.1f}%
            </div>
            <div class="metric">
                <strong>平均内存使用率:</strong> {avg_memory:.1f}%
            </div>
            <div class="metric">
                <strong>峰值内存使用率:</strong> {max_memory:.1f}%
            </div>
            <div class="metric">
                <strong>平均TCP连接数:</strong> {avg_tcp_conns:.0f}
            </div>
            <div class="metric">
                <strong>峰值TCP连接数:</strong> {max_tcp_conns}
            </div>
        </div>
        """
    
    def _generate_redis_metrics_section(self, redis_metrics: List[RedisMetrics]) -> str:
        """生成Redis性能指标部分"""
        if not redis_metrics:
            return ""
        
        # 计算Redis统计信息
        ops_values = [m.instantaneous_ops_per_sec for m in redis_metrics]
        memory_values = [m.used_memory_mb for m in redis_metrics]
        hit_rate_values = [m.hit_rate for m in redis_metrics]
        
        avg_ops = sum(ops_values) / len(ops_values)
        max_ops = max(ops_values)
        avg_memory = sum(memory_values) / len(memory_values)
        max_memory = max(memory_values)
        avg_hit_rate = sum(hit_rate_values) / len(hit_rate_values) * 100
        
        return f"""
        <h2>Redis性能指标</h2>
        <div class="summary">
            <div class="metric">
                <strong>平均OPS:</strong> {avg_ops:.0f}
            </div>
            <div class="metric">
                <strong>峰值OPS:</strong> {max_ops}
            </div>
            <div class="metric">
                <strong>平均内存使用:</strong> {avg_memory:.1f}MB
            </div>
            <div class="metric">
                <strong>峰值内存使用:</strong> {max_memory:.1f}MB
            </div>
            <div class="metric">
                <strong>平均命中率:</strong> {avg_hit_rate:.1f}%
            </div>
        </div>
        """
    
    def _generate_database_metrics_section(self, db_metrics: List[DatabaseMetrics]) -> str:
        """生成数据库性能指标部分"""
        if not db_metrics:
            return ""
        
        return "<h2>数据库性能指标</h2><p>数据库性能监控数据已收集</p>"
    
    def _generate_application_metrics_section(self, app_metrics: List[ApplicationMetrics]) -> str:
        """生成应用程序性能指标部分"""
        if not app_metrics:
            return ""
        
        return "<h2>应用程序性能指标</h2><p>应用程序性能监控数据已收集</p>"
    
    def _generate_recommendations(self, test_results: List[Dict], system_metrics: List[SystemMetrics]) -> str:
        """生成建议和结论"""
        recommendations = ["<ul>"]
        
        # 基于测试结果生成建议
        if test_results:
            avg_success_rate = sum(r.get('message_success_rate', 0) for r in test_results) / len(test_results)
            if avg_success_rate < 0.95:
                recommendations.append("<li>消息成功率较低，建议检查网络连接和服务器配置</li>")
            
            avg_response_time = sum(r.get('avg_response_time', 0) for r in test_results) / len(test_results) * 1000
            if avg_response_time > 100:
                recommendations.append("<li>响应时间较长，建议优化代码性能或增加服务器资源</li>")
        
        # 基于系统指标生成建议
        if system_metrics:
            avg_cpu = sum(m.cpu_percent for m in system_metrics) / len(system_metrics)
            if avg_cpu > 80:
                recommendations.append("<li>CPU使用率较高，建议增加CPU资源或优化代码</li>")
            
            avg_memory = sum(m.memory_percent for m in system_metrics) / len(system_metrics)
            if avg_memory > 80:
                recommendations.append("<li>内存使用率较高，建议增加内存或检查内存泄漏</li>")
        
        if len(recommendations) == 1:
            recommendations.append("<li>系统性能表现良好，无明显问题</li>")
        
        recommendations.append("</ul>")
        return "".join(recommendations)
    
    def _format_duration(self, metrics: List[SystemMetrics]) -> str:
        """格式化持续时间"""
        if not metrics or len(metrics) < 2:
            return "未知"
        
        duration = metrics[-1].timestamp - metrics[0].timestamp
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟{seconds}秒"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"
    
    def _export_csv_data(self, test_results: List[Dict], 
                        system_metrics: List[SystemMetrics],
                        redis_metrics: List[RedisMetrics] = None,
                        db_metrics: List[DatabaseMetrics] = None,
                        app_metrics: List[ApplicationMetrics] = None,
                        report_time: str = ""):
        """导出CSV数据文件"""
        
        # 导出测试结果
        if test_results:
            csv_file = f"{self.output_dir}/test_results_{report_time}.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                if test_results:
                    writer = csv.DictWriter(f, fieldnames=test_results[0].keys())
                    writer.writeheader()
                    writer.writerows(test_results)
        
        # 导出系统指标
        if system_metrics:
            csv_file = f"{self.output_dir}/system_metrics_{report_time}.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=asdict(system_metrics[0]).keys())
                writer.writeheader()
                for metric in system_metrics:
                    writer.writerow(asdict(metric))
    
    def _generate_charts(self, system_metrics: List[SystemMetrics],
                        redis_metrics: List[RedisMetrics] = None,
                        db_metrics: List[DatabaseMetrics] = None,
                        app_metrics: List[ApplicationMetrics] = None,
                        report_time: str = ""):
        """生成性能图表"""
        try:
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 系统性能图表
            if system_metrics:
                self._create_system_charts(system_metrics, report_time)
            
            # Redis性能图表
            if redis_metrics:
                self._create_redis_charts(redis_metrics, report_time)
                
        except Exception as e:
            logger.warning(f"生成图表失败: {e}")
    
    def _create_system_charts(self, system_metrics: List[SystemMetrics], report_time: str):
        """创建系统性能图表"""
        timestamps = [datetime.fromtimestamp(m.timestamp) for m in system_metrics]
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # CPU使用率
        cpu_values = [m.cpu_percent for m in system_metrics]
        ax1.plot(timestamps, cpu_values, 'b-', linewidth=2)
        ax1.set_title('CPU使用率')
        ax1.set_ylabel('使用率 (%)')
        ax1.grid(True)
        
        # 内存使用率
        memory_values = [m.memory_percent for m in system_metrics]
        ax2.plot(timestamps, memory_values, 'r-', linewidth=2)
        ax2.set_title('内存使用率')
        ax2.set_ylabel('使用率 (%)')
        ax2.grid(True)
        
        # TCP连接数
        tcp_values = [m.tcp_connections for m in system_metrics]
        ax3.plot(timestamps, tcp_values, 'g-', linewidth=2)
        ax3.set_title('TCP连接数')
        ax3.set_ylabel('连接数')
        ax3.grid(True)
        
        # 网络IO
        network_sent = [m.network_sent_mb for m in system_metrics]
        network_recv = [m.network_recv_mb for m in system_metrics]
        ax4.plot(timestamps, network_sent, 'orange', label='发送', linewidth=2)
        ax4.plot(timestamps, network_recv, 'purple', label='接收', linewidth=2)
        ax4.set_title('网络IO')
        ax4.set_ylabel('MB/s')
        ax4.legend()
        ax4.grid(True)
        
        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/system_performance_{report_time}.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_redis_charts(self, redis_metrics: List[RedisMetrics], report_time: str):
        """创建Redis性能图表"""
        timestamps = [datetime.fromtimestamp(m.timestamp) for m in redis_metrics]
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # OPS
        ops_values = [m.instantaneous_ops_per_sec for m in redis_metrics]
        ax1.plot(timestamps, ops_values, 'b-', linewidth=2)
        ax1.set_title('Redis OPS')
        ax1.set_ylabel('操作/秒')
        ax1.grid(True)
        
        # 内存使用
        memory_values = [m.used_memory_mb for m in redis_metrics]
        ax2.plot(timestamps, memory_values, 'r-', linewidth=2)
        ax2.set_title('Redis内存使用')
        ax2.set_ylabel('内存 (MB)')
        ax2.grid(True)
        
        # 命中率
        hit_rate_values = [m.hit_rate * 100 for m in redis_metrics]
        ax3.plot(timestamps, hit_rate_values, 'g-', linewidth=2)
        ax3.set_title('Redis命中率')
        ax3.set_ylabel('命中率 (%)')
        ax3.grid(True)
        
        # Stream和Queue长度
        stream_length = [m.stream_length for m in redis_metrics]
        list_length = [m.list_length for m in redis_metrics]
        ax4.plot(timestamps, stream_length, 'orange', label='Stream长度', linewidth=2)
        ax4.plot(timestamps, list_length, 'purple', label='Queue长度', linewidth=2)
        ax4.set_title('队列长度')
        ax4.set_ylabel('消息数')
        ax4.legend()
        ax4.grid(True)
        
        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/redis_performance_{report_time}.png", dpi=300, bbox_inches='tight')
        plt.close()


if __name__ == "__main__":
    # 测试性能监控
    system_monitor = SystemMonitor(interval=1.0)
    redis_monitor = RedisMonitor(interval=5.0)
    
    print("开始性能监控...")
    system_monitor.start()
    redis_monitor.start()
    
    # 运行30秒
    time.sleep(30)
    
    print("停止监控...")
    system_monitor.stop()
    redis_monitor.stop()
    
    # 生成报告
    report_generator = PerformanceReportGenerator()
    system_metrics = system_monitor.get_metrics()
    redis_metrics = redis_monitor.get_metrics()
    
    # 模拟测试结果
    test_results = [{
        'test_name': 'Test',
        'total_devices': 10,
        'connection_success_rate': 0.95,
        'message_success_rate': 0.98,
        'messages_per_second': 100.0,
        'avg_response_time': 0.05,
        'p95_response_time': 0.1,
        'duration': 30.0
    }]
    
    report_file = report_generator.generate_comprehensive_report(
        test_results, system_metrics, redis_metrics
    )
    
    print(f"性能报告已生成: {report_file}")
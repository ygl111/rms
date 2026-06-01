#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本
提供简化的命令行接口来运行常见的性能测试
"""

import os
import sys
import subprocess
import argparse

def run_command(command, description):
    """运行命令并显示描述"""
    print(f"\n🚀 {description}")
    print(f"执行命令: {command}")
    print("-" * 50)
    
    result = subprocess.run(command, shell=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - 完成")
    else:
        print(f"❌ {description} - 失败")
    
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="性能测试快速启动工具")
    parser.add_argument("--env", default="local", choices=["local", "vm", "staging"], 
                       help="测试环境: local(本地), vm(虚拟机192.168.12.118), staging(测试环境)")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 烟雾测试
    smoke_parser = subparsers.add_parser("smoke", help="运行烟雾测试")
    
    # 负载测试
    load_parser = subparsers.add_parser("load", help="运行负载测试")
    
    # 压力测试
    stress_parser = subparsers.add_parser("stress", help="运行压力测试")
    
    # 并发测试
    concurrent_parser = subparsers.add_parser("concurrent", help="运行并发连接测试")
    
    # 完整测试套件
    full_parser = subparsers.add_parser("full", help="运行完整测试套件")
    
    # 单设备测试
    single_parser = subparsers.add_parser("single", help="运行单设备测试")
    single_parser.add_argument("--device-id", default="TEST_DEVICE_001", help="设备ID")
    single_parser.add_argument("--host", default="127.0.0.1", help="服务器地址")
    single_parser.add_argument("--port", type=int, default=8081, help="服务器端口")
    
    # 监控模式
    monitor_parser = subparsers.add_parser("monitor", help="仅运行性能监控")
    monitor_parser.add_argument("--duration", type=int, default=300, help="监控时长(秒)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("❌ 需要Python 3.7或更高版本")
        return
    
    # 检查依赖
    try:
        import psutil
        import redis
        import matplotlib
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    print("🔧 金融设备通信系统性能测试工具")
    print("=" * 50)
    
    # 根据命令执行相应操作
    if args.command == "smoke":
        success = run_command(
            f"python main_test_runner.py --test smoke_test --env {args.env}",
            "执行烟雾测试"
        )
    
    elif args.command == "load":
        success = run_command(
            f"python main_test_runner.py --test load_test --env {args.env}",
            "执行负载测试"
        )
    
    elif args.command == "stress":
        success = run_command(
            f"python main_test_runner.py --test stress_test --env {args.env}",
            "执行压力测试"
        )
    
    elif args.command == "concurrent":
        success = run_command(
            f"python main_test_runner.py --test concurrent_test --env {args.env}",
            "执行并发连接测试"
        )
    
    elif args.command == "full":
        success = run_command(
            f"python main_test_runner.py --full --env {args.env}",
            "执行完整测试套件"
        )
    
    elif args.command == "single":
        print(f"\n🔧 运行单设备测试")
        print(f"设备ID: {args.device_id}")
        print(f"服务器: {args.host}:{args.port}")
        
        command = f"python -c \""
        command += f"from device_simulator import *; "
        command += f"config = DeviceConfig('{args.device_id}'); "
        command += f"conn = ConnectionConfig('{args.host}', {args.port}); "
        command += f"sim = DeviceSimulator(config, conn); "
        command += f"sim.connect() and sim.perform_registration() and sim.perform_authentication(); "
        command += f"sim.send_heartbeat(); sim.send_banknote_report(); "
        command += f"print('单设备测试完成')\""
        
        success = run_command(command, "单设备功能测试")
    
    elif args.command == "monitor":
        command = f"python -c \""
        command += f"from performance_monitor import *; "
        command += f"import time; "
        command += f"sm = SystemMonitor(); rm = RedisMonitor(); "
        command += f"sm.start(); rm.start(); "
        command += f"print('监控运行中...'); time.sleep({args.duration}); "
        command += f"sm.stop(); rm.stop(); "
        command += f"print('监控完成')\""
        
        success = run_command(command, f"运行 {args.duration} 秒性能监控")
    
    else:
        print(f"❌ 未知命令: {args.command}")
        return
    
    if success:
        print(f"\n✅ 所有操作完成!")
        print("📊 请查看 performance_reports 目录下的测试报告")
    else:
        print(f"\n❌ 操作失败，请检查日志")

if __name__ == "__main__":
    main()
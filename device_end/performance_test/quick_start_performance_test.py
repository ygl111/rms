#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能测试快速启动脚本
一键准备设备数据并启动性能测试
"""

import os
import sys
import subprocess
import time
import argparse
import json
from typing import Dict, List

def run_command(cmd: List[str], description: str) -> bool:
    """运行命令并显示结果"""
    print(f"\n🔄 {description}...")
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print(f"✅ {description} 成功")
            if result.stdout.strip():
                # 只显示关键输出行
                lines = result.stdout.strip().split('\n')
                for line in lines[-10:]:  # 显示最后10行
                    if any(keyword in line for keyword in ['成功', '✅', '❌', '错误', '失败', '完成']):
                        print(f"   {line}")
            return True
        else:
            print(f"❌ {description} 失败")
            if result.stderr.strip():
                print(f"错误信息: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ {description} 执行异常: {e}")
        return False

def check_dependencies() -> bool:
    """检查依赖"""
    print("🔍 检查依赖包...")
    
    required_packages = ['pymysql', 'json', 'socket', 'threading']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'pymysql':
                import pymysql
            elif package == 'json':
                import json
            elif package == 'socket':
                import socket
            elif package == 'threading':
                import threading
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print(f"请运行: pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ 依赖包检查通过")
    return True

def check_files() -> bool:
    """检查必要文件"""
    print("🔍 检查必要文件...")
    
    required_files = [
        'test_config.json',
        'device_batch_inserter.py',
        'enhanced_device_simulator.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
        return False
    
    print("✅ 文件检查通过")
    return True

def load_config(config_file: str, environment: str) -> Dict:
    """加载配置"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if environment not in config['test_environments']:
            raise ValueError(f"环境 '{environment}' 不存在")
        
        return config['test_environments'][environment]
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return {}

def test_database_connection(config: Dict) -> bool:
    """测试数据库连接"""
    print("🔍 测试数据库连接...")
    
    try:
        import pymysql
        
        db_config = config.get('database', {})
        connection = pymysql.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            charset='utf8mb4',
            connect_timeout=5
        )
        connection.close()
        print("✅ 数据库连接成功")
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("请检查数据库配置和网络连接")
        return False

def main():
    parser = argparse.ArgumentParser(description="性能测试快速启动脚本")
    parser.add_argument("--device-count", type=int, default=100, help="要创建的设备数量")
    parser.add_argument("--device-prefix", type=str, default="PERF_TEST", help="设备ID前缀")
    parser.add_argument("--environment", type=str, default="local", choices=["local", "vm", "staging"], help="环境名称")
    parser.add_argument("--config", type=str, default="test_config.json", help="配置文件路径")
    parser.add_argument("--cleanup", action="store_true", help="清理现有测试设备")
    parser.add_argument("--skip-preparation", action="store_true", help="跳过设备准备，直接开始测试")
    parser.add_argument("--test-duration", type=int, default=120, help="测试持续时间(秒)")
    parser.add_argument("--concurrent-devices", type=int, default=10, help="并发测试设备数量")
    parser.add_argument("--registration-interval", type=float, default=0.1, help="设备注册间隔(秒)")
    parser.add_argument("--heartbeat-interval", type=int, default=30, help="心跳间隔(秒)")
    parser.add_argument("--test-messages", type=int, default=5, help="每个设备发送的测试消息数量")
    
    args = parser.parse_args()
    
    print("🚀 性能测试快速启动脚本")
    print("=" * 60)
    print(f"设备数量: {args.device_count}")
    print(f"设备前缀: {args.device_prefix}")
    print(f"测试环境: {args.environment}")
    print(f"并发设备: {args.concurrent_devices}")
    print(f"测试时长: {args.test_duration}秒")
    print("=" * 60)
    
    # 1. 检查依赖和文件
    if not check_dependencies() or not check_files():
        return False
    
    # 2. 加载和验证配置
    config = load_config(args.config, args.environment)
    if not config:
        return False
    
    # 3. 测试数据库连接
    if not test_database_connection(config):
        return False
    
    # 4. 准备设备数据（如果需要）
    if not args.skip_preparation:
        device_prep_cmd = [
            sys.executable, "device_batch_inserter.py",
            "--count", str(args.device_count),
            "--prefix", args.device_prefix,
            "--environment", args.environment,
            "--config", args.config
        ]
        
        if args.cleanup:
            device_prep_cmd.append("--cleanup")
        
        if not run_command(device_prep_cmd, "准备测试设备数据"):
            print("❌ 设备数据准备失败，无法继续测试")
            return False
    else:
        print("⏭️  跳过设备数据准备")
    
    # 5. 启动性能测试
    test_cmd = [
        sys.executable, "enhanced_device_simulator.py",
        "--environment", args.environment,
        "--config", args.config,
        "--device-count", str(args.concurrent_devices),
        "--device-prefix", args.device_prefix,
        "--registration-interval", str(args.registration_interval),
        "--heartbeat-interval", str(args.heartbeat_interval),
        "--test-messages", str(args.test_messages),
        "--test-duration", str(args.test_duration)
    ]
    
    if not run_command(test_cmd, "执行性能测试"):
        print("❌ 性能测试执行失败")
        return False
    
    print("\n🎉 性能测试完成!")
    print("📊 测试报告和日志文件已保存")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        exit(1)
    except Exception as e:
        print(f"\n❌ 程序执行错误: {e}")
        exit(1)
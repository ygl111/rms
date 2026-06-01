#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看数据库中现有的测试设备
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from enhanced_device_simulator import DeviceRepository, DatabaseConfig
    
    def list_test_devices():
        """列出数据库中的测试设备"""
        print("=== 查看数据库中的测试设备 ===")
        
        # 加载配置
        try:
            with open("test_config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            db_config = DatabaseConfig(**config['test_environments']['local']['database'])
            repository = DeviceRepository(db_config)
            
            if not repository.connect():
                print("❌ 数据库连接失败")
                return
            
            # 查询测试设备
            devices = repository.load_test_devices("PERF_TEST", limit=10)
            
            if devices:
                print(f"✅ 找到 {len(devices)} 个测试设备:")
                for i, device in enumerate(devices, 1):
                    print(f"  {i}. {device.device_id} - {device.device_model}")
                print(f"\n建议使用第一个设备ID: {devices[0].device_id}")
            else:
                print("❌ 没有找到测试设备")
                print("请先运行: python device_batch_inserter.py --count 10 --prefix PERF_TEST")
            
            repository.disconnect()
            
        except Exception as e:
            print(f"❌ 查询失败: {e}")
    
    if __name__ == "__main__":
        list_test_devices()

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在正确的目录中运行此脚本")
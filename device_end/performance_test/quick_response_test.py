#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证响应时间统计功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from comprehensive_performance_test import ComprehensivePerformanceTestRunner
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger('QuickResponseTimeTest')

def main():
    """快速测试响应时间功能"""
    logger.info("🚀 开始快速响应时间验证测试")
    
    runner = ComprehensivePerformanceTestRunner("test_config.json")
    
    try:
        # 运行基础测试（现在包含消息发送）
        logger.info("📨 运行包含消息发送的基础测试...")
        success = runner.run_basic_performance_test(device_count=3, test_duration=30)
        
        if success:
            logger.info("✅ 基础测试完成，响应时间应该有数据了")
        else:
            logger.error("❌ 基础测试失败")
            
    except Exception as e:
        logger.error(f"💥 测试过程中发生错误: {e}")
    finally:
        runner.cleanup()

if __name__ == "__main__":
    main()
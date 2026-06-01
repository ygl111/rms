#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备连接性能优化使用指南
说明如何使用新的并发连接功能
"""

print("""
🚀 设备连接性能优化使用指南
================================================================================

📋 问题解决方案：
之前的设备连接是串行的，每个设备约1秒，1000个设备需要约17分钟。
现在优化为并发连接，可以在几十秒内完成1000个设备的连接！

🛠️ 使用方法：

1️⃣  使用增强版设备仿真器（支持并发）：
   python enhanced_device_simulator.py \\
       --device-count 1000 \\
       --max-concurrent 100 \\
       --registration-interval 0.01

2️⃣  使用专门的快速并发测试器：
   python fast_concurrent_test.py \\
       --devices 1000 \\
       --concurrent 100 \\
       --prefix FAST_TEST

📊 性能对比：

   串行连接（优化前）：
   - 1000设备 ≈ 1000秒 ≈ 17分钟
   - 10000设备 ≈ 10000秒 ≈ 2.8小时

   并发连接（优化后）：
   - 1000设备 ≈ 20-60秒
   - 10000设备 ≈ 3-5分钟

⚡ 关键优化：

1. 并发处理：使用ThreadPoolExecutor并发连接
2. 批量处理：避免系统过载
3. 超时优化：更短的连接和响应超时
4. 进度监控：实时显示连接进度

🔧 参数说明：

--max-concurrent / --concurrent：
   - 最大并发连接数
   - 建议值：50-200（根据系统性能调整）
   - 过高可能导致系统过载

--registration-interval：
   - 连接间隔时间
   - 并发模式下可以设置很小（0.001-0.01）
   - 用于避免瞬间过载

--timeout：
   - 单个连接的超时时间
   - 建议值：5-15秒
   - 过短可能导致网络慢时连接失败

📈 测试建议：

小规模测试（验证功能）：
   python fast_concurrent_test.py --devices 100 --concurrent 20

中规模测试（性能评估）：
   python fast_concurrent_test.py --devices 1000 --concurrent 50

大规模测试（压力测试）：
   python fast_concurrent_test.py --devices 10000 --concurrent 100

📝 测试报告：

测试完成后会生成：
- 控制台实时报告
- JSON详细报告文件
- 包含每个设备的详细时间统计

报告包含：
- 成功率统计
- 连接速度（设备/秒）
- 平均连接/注册/鉴权时间
- 错误详情

⚠️  注意事项：

1. 确保TCP网关已启动并正常运行
2. 确保数据库中有足够的测试设备
3. 监控系统资源使用情况
4. 根据网络和硬件情况调整并发数
5. 大规模测试前先进行小规模验证

🎯 预期性能：

在正常硬件配置下：
- 100个设备：5-10秒
- 1000个设备：30-60秒  
- 10000个设备：3-8分钟

成功率应该在95%以上。

================================================================================
""")

def run_quick_test():
    """运行快速测试"""
    import subprocess
    import sys
    
    print("🧪 开始快速功能验证...")
    
    try:
        # 运行小规模测试
        result = subprocess.run([
            sys.executable, "fast_concurrent_test.py",
            "--devices", "50",
            "--concurrent", "10",
            "--prefix", "QUICK_TEST"
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✅ 快速测试完成！")
            print(result.stdout)
        else:
            print("❌ 快速测试失败：")
            print(result.stderr)
    
    except subprocess.TimeoutExpired:
        print("⏰ 快速测试超时")
    except FileNotFoundError:
        print("❌ 找不到测试脚本，请确保在正确的目录下运行")
    except Exception as e:
        print(f"❌ 测试异常：{e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick-test":
        run_quick_test()
    else:
        print("💡 提示：运行 'python performance_guide.py --quick-test' 进行快速功能验证")
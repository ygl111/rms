# 金融设备运维系统 - 性能测试套件

## 📋 项目概述

这是一个专为金融设备运维系统设计的综合性能测试套件，用于测试TCP Gateway和协议解析器的性能、稳定性和并发处理能力。该系统支持多种协议（DP Protocol V1/V2、Modbus TCP等）和多种设备类型的性能测试。

## ✨ 主要功能

### 🔧 核心功能模块

1. **设备仿真器** (`enhanced_device_simulator.py`)
   - 模拟各种金融设备（ATM、CRS、CDM等）
   - 支持完整的设备生命周期：注册、鉴权、心跳、业务消息
   - 支持多种消息类型：故障上报、点钞上报、状态查询等

2. **负载测试器** (`load_tester.py`)
   - 多线程并发连接测试
   - 压力测试和性能基准测试
   - 自动化测试场景和参数调优

3. **综合性能测试** (`comprehensive_performance_test.py`)
   - 端到端完整测试流程
   - 多维度性能指标收集
   - 自动化测试报告生成

4. **性能监控器** (`performance_monitor.py`)
   - 系统资源监控（CPU、内存、网络）
   - 数据库性能监控
   - Redis缓存性能监控
   - 应用层性能指标收集

5. **并发测试器** (`concurrent_tester.py`)
   - 大规模并发连接测试
   - 连接池管理和优化
   - 并发场景压力测试

6. **设备批量管理** (`device_batch_inserter.py`)
   - 批量创建测试设备数据
   - 设备数据管理和清理
   - 支持多环境配置

### 📊 测试类型

- **连接性能测试**: 测试TCP连接建立和断开性能
- **注册流程测试**: 测试设备注册和鉴权流程
- **消息处理测试**: 测试各种业务消息的处理性能
- **并发压力测试**: 测试系统在高并发场景下的表现
- **稳定性测试**: 长时间运行稳定性验证
- **资源消耗测试**: 系统资源使用情况监控

## 🚀 快速开始

### 环境要求

- Python 3.8+
- MySQL 5.7+
- Redis 6.0+ (可选)
- Windows/Linux/macOS

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基础配置

1. **配置数据库连接**

编辑 `test_config.json`:

```json
{
  "test_environments": {
    "local": {
      "database": {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "your_username",
        "password": "your_password",
        "database": "rms"
      },
      "tcp_gateway": {
        "host": "127.0.0.1",
        "ports": {
          "dp_protocol_v1": 8081,
          "dp_protocol_v2": 8082,
          "modbus_tcp": 502
        }
      }
    }
  }
}
```

2. **初始化数据库**

```bash
# 导入数据库结构
mysql -u username -p database_name < rms1.8.sql
```

### 一键启动测试

```bash
# 快速启动完整性能测试
python quick_start_performance_test.py

# 自定义参数启动
python quick_start_performance_test.py \
    --device-count 100 \
    --concurrent-devices 20 \
    --test-duration 300 \
    --environment local
```

## 📖 详细使用指南

### 1. 设备数据准备

```bash
# 创建1000个测试设备
python device_batch_inserter.py --count 1000

# 指定设备前缀和环境
python device_batch_inserter.py \
    --count 500 \
    --prefix "PERF_TEST" \
    --environment vm

# 清理测试设备
python device_batch_inserter.py --cleanup
```

### 2. 基础性能测试

```bash
# 运行基础性能测试
python comprehensive_performance_test.py \
    --test-type basic \
    --devices 50 \
    --duration 120 \
    --device-prefix "PERF_TEST"

# 运行压力测试
python comprehensive_performance_test.py \
    --test-type comprehensive \
    --devices 200 \
    --duration 600 \
    --device-prefix "PERF_100K"
```

### 3. 负载测试

```bash
# load_tester.py 主要作为模块使用，可以通过编程方式调用
# 或者使用 comprehensive_performance_test.py 进行各种测试

# 综合压力测试
python comprehensive_performance_test.py \
    --test-type comprehensive \
    --devices 500 \
    --duration 1800

# 心跳压力测试
python comprehensive_performance_test.py \
    --test-type heartbeat \
    --devices 1000 \
    --duration 600 \
    --heartbeat-interval 10
```

### 4. 完整测试套件

```bash
# 运行完整测试套件
python main_test_runner.py \
    --full \
    --env local \
    --log-level INFO

# 运行单个测试
python main_test_runner.py \
    --test stress_test \
    --env local \
    --config test_config.json

# 运行并发测试
python main_test_runner.py \
    --test concurrent_test \
    --env local
```

## 📈 性能指标

### 连接性能指标
- **连接建立时间**: 平均/最大连接建立耗时
- **连接成功率**: 成功连接数/总尝试连接数
- **并发连接数**: 同时维持的TCP连接数量

### 业务性能指标
- **注册成功率**: 设备注册成功的比例
- **鉴权响应时间**: 设备鉴权流程耗时
- **消息处理吞吐量**: 每秒处理的消息数量
- **平均响应时间**: 消息平均响应时间

### 系统性能指标
- **CPU使用率**: 系统CPU资源消耗
- **内存使用率**: 内存资源占用情况
- **网络I/O**: 网络带宽使用情况
- **数据库性能**: 数据库连接数、查询耗时

## 📊 测试报告

测试完成后会自动生成详细的性能报告：

- **HTML报告**: 包含图表和详细分析的可视化报告
- **CSV数据**: 原始测试数据，便于进一步分析
- **性能图表**: 性能趋势和对比图表
- **错误日志**: 详细的错误信息和堆栈跟踪

报告保存位置：`./performance_reports/`

## 🔧 高级配置

### 自定义测试场景

创建自定义测试配置文件：

```json
{
  "test_scenarios": {
    "peak_load": {
      "device_count": 1000,
      "concurrent_devices": 200,
      "test_duration": 1800,
      "message_types": ["heartbeat", "fault_report", "banknote_report"],
      "message_intervals": {
        "heartbeat": 30,
        "fault_report": 300,
        "banknote_report": 60
      }
    }
  }
}
```

### 监控配置

启用详细监控：

```bash
python main_test_runner.py \
    --full \
    --env local \
    --log-level DEBUG \
    --log-file detailed_performance.log
```

## 🛠️ 故障排查

### 常见问题

1. **数据库连接失败**
   ```bash
   # 检查数据库连接
   python -c "from device_batch_inserter import *; test_db_connection()"
   ```

2. **TCP Gateway连接失败**
   ```bash
   # 测试网关连通性
   python network_test.py --host 127.0.0.1 --port 8081
   ```

3. **性能测试异常**
   ```bash
   # 启用调试模式
   python comprehensive_performance_test.py \
       --test-type basic \
       --devices 10 \
       --duration 60 \
       --config test_config.json
   ```

### 日志分析

查看详细日志：
```bash
# 查看测试日志
tail -f performance_test.log

# 查看错误日志
grep "ERROR\|CRITICAL" performance_test.log
```

## 📁 项目结构

```
performance_test/
├── README.md                          # 项目说明文档
├── requirements.txt                   # Python依赖包
├── test_config.json                   # 测试配置文件
├── rms1.8.sql                        # 数据库结构文件
├── start_performance_test.bat         # Windows启动脚本
│
├── 核心测试模块/
│   ├── comprehensive_performance_test.py    # 综合性能测试
│   ├── main_test_runner.py                 # 主测试运行器
│   ├── load_tester.py                      # 负载测试器
│   ├── concurrent_tester.py                # 并发测试器
│   └── performance_monitor.py              # 性能监控器
│
├── 设备仿真模块/
│   ├── enhanced_device_simulator.py        # 增强设备仿真器
│   └── device_batch_inserter.py           # 设备批量管理
│
├── 快速启动模块/
│   ├── quick_start_performance_test.py     # 快速启动脚本
│   ├── quick_start.py                      # 简单启动脚本
│   └── quick_response_test.py              # 快速响应测试
│
├── 网络测试模块/
│   ├── network_test.py                     # 网络连接测试
│   └── network_diagnosis.py               # 网络诊断工具
│
├── 工具脚本/
│   ├── list_test_devices.py               # 列出测试设备
│   ├── find_vm_ip.py                      # 查找虚拟机IP
│   ├── update_vm_ip.py                    # 更新虚拟机IP
│   └── examples.py                        # 示例代码
│
└── 测试结果/
    └── performance_reports/               # 测试报告目录
        ├── *.html                        # HTML格式报告
        └── *.csv                         # CSV数据文件
```

## 🤝 参与贡献

欢迎提交Issue和Pull Request来改进这个项目！

### 开发指南

1. Fork项目到你的GitHub账户
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交变更：`git commit -am 'Add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交Pull Request

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 📞 技术支持

如有问题或建议，请联系开发团队或提交Issue。

---

**注意**: 在生产环境中使用前，请确保充分测试所有配置和参数设置。
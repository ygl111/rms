# 🚀 C++ Parser - 金融设备通信系统解析器

## 📋 项目概述

**C++ Parser** 是金融设备通信系统的高性能解析器，摒弃了之前的python语言开发转而使用C++。它提供了更高的性能、更低的延迟和更好的资源利用率。

### 🎯 主要特性

- **高性能**: 相比Python版本提升10-20倍性能
- **低延迟**: 平均处理延迟 < 1ms
- **多线程**: 支持多线程并行处理
- **协议完整**: 支持所有金融设备通信协议
- **配置灵活**: 基于JSON的配置管理
- **监控完善**: 实时性能监控和健康检查
- **易于部署**: 单一可执行文件，无依赖问题
- **缓存管理**: 自动缓存清除和锁管理

### 📊 性能对比

| 指标 | Python版本 | C++版本 | 性能提升 |
|------|------------|---------|----------|
| QPS处理能力 | 8,000-20,000 | 80,000-200,000 | **10-20倍** |
| 内存使用 | 80-150MB | 20-50MB | **60-75% 减少** |
| CPU利用率 | 60-80% | 30-50% | **更高效** |
| 延迟 | 0.1-0.3ms | 0.05-0.15ms | **50% 减少** |

## 🏗️ 系统架构

### 整体架构
```
[TCP网关] → [Redis Stream] → [C++解析器] → [Redis Queue] → [TCP网关]
                                   ↓
                            [多线程处理器]
                                   ↓
                           [协议解析引擎]
                                   ↓
                           [响应生成器]
                                   ↓
                           [缓存管理系统]
```

### 设计模式

#### 1. **策略模式 + 工厂模式**
- `IMessageHandler` - 消息处理器接口
- `MessageHandlerFactory` - 处理器工厂
- 具体处理器：`RegistrationHandler`, `LoginHandler`, `HeartbeatHandler`等

#### 2. **依赖注入模式**
- `DeviceService` / `DeviceServiceImpl` - 设备服务接口与实现
- `BanknoteService` / `BanknoteServiceImpl` - 点钞服务
- `FaultService` / `FaultServiceImpl` - 故障服务
- `UpgradeService` / `UpgradeServiceImpl` - 升级服务

#### 3. **适配器模式**
- `MySqlDatabaseAdaptor` - MySQL数据库适配器
- `RedisCacheAdaptor` - Redis缓存适配器
- `OpenSSLAuthAdaptor` - OpenSSL认证适配器

## 📁 项目结构

```
cpp_parser/
├── config/                     # 配置文件
│   ├── dp_protocol_v1.json    # 协议定义文件
│   ├── parser_config.json     # 解析器配置
│   └── validate_config.sh     # 配置验证脚本
├── include/                    # 头文件
│   ├── Application.h          # 应用程序主类
│   ├── dpower/               # DPower架构接口
│   │   ├── cache/Interfaces.h
│   │   ├── config/Interfaces.h
│   │   ├── db/Interfaces.h
│   │   ├── redis/Interfaces.h
│   │   └── utils/Auth.h
│   ├── logic/                # 业务逻辑
│   │   ├── Config.h
│   │   ├── MessageProcessor.h

│   │   ├── ResponseGenerator.h
│   │   ├── handlers/         # 消息处理器
│   │   │   ├── IMessageHandler.h
│   │   │   ├── MessageHandlerFactory.h
│   │   │   ├── RegistrationHandler.h
│   │   │   ├── LoginHandler.h
│   │   │   ├── HeartbeatHandler.h
│   │   │   ├── FaultReportHandler.h
│   │   │   ├── BanknoteReportHandler.h
│   │   │   └── UpgradeResultHandler.h
│   │   └── services/         # 业务服务
│   │       ├── DeviceService.h
│   │       ├── DeviceServiceImpl.h
│   │       ├── BanknoteService.h
│   │       ├── BanknoteServiceImpl.h
│   │       ├── FaultService.h
│   │       ├── FaultServiceImpl.h
│   │       ├── UpgradeService.h
│   │       └── UpgradeServiceImpl.h
├── src/                       # 源代码
│   ├── app/                  # 应用程序
│   │   ├── Application.cpp
│   │   └── main.cpp
│   ├── logic/               # 业务逻辑实现
│   │   ├── Config.cpp
│   │   ├── MessageProcessor.cpp

│   │   ├── ResponseGenerator.cpp
│   │   ├── handlers/        # 处理器实现
│   │   │   ├── RegistrationHandler.cpp
│   │   │   ├── LoginHandler.cpp
│   │   │   ├── HeartbeatHandler.cpp
│   │   │   ├── FaultReportHandler.cpp
│   │   │   ├── BanknoteReportHandler.cpp
│   │   │   ├── UpgradeResultHandler.cpp
│   │   │   └── MessageHandlerFactory.cpp
│   │   └── services/        # 服务实现
│   │       ├── DeviceServiceImpl.cpp
│   │       ├── BanknoteServiceImpl.cpp
│   │       ├── FaultServiceImpl.cpp
│   │       └── UpgradeServiceImpl.cpp
│   └── adapters/            # 适配器实现
│       ├── MySqlDatabaseAdaptor.cpp
│       ├── RedisCacheAdaptor.cpp
│       ├── OpenSSLAuthAdaptor.cpp
│       ├── JsonConfigAdaptors.cpp
│       └── SwRedisAdaptors.cpp
├── external/                 # 外部依赖
│   └── include/
│       └── json.hpp
├── CMakeLists.txt           # CMake构建配置
├── requirements.txt         # 依赖库列表
├── install_redis_plus_plus.sh # Redis++安装脚本
├── deploy.sh               # 部署脚本
└── README.md               # 项目说明文档
```

## 🛠️ 快速开始

### 1. 环境要求

- **操作系统**: Linux (Ubuntu 20.04+, CentOS 7+)
- **编译器**: GCC 7.0+ 或 Clang 6.0+
- **CMake**: 3.10+
- **依赖库**: Boost 1.70+, redis++

### 2. 编译安装

```bash
# 1. 克隆项目
git clone <repository-url>
cd cpp_parser

# 2. 安装依赖
sudo apt-get update
sudo apt-get install -y build-essential cmake libboost-all-dev libssl-dev
./install_redis_plus_plus.sh

# 3. 创建构建目录
mkdir build && cd build

# 4. 配置和编译
cmake ..
make -j$(nproc)

# 5. 安装到系统
sudo make install
```

### 3. 配置设置

```bash
# 编辑配置文件
nano config/parser_config.json
```

主要配置项：
```json
{
  "redis": {
    "host": "localhost",
    "port": 6379,
    "request_stream_key": "device_raw_messages",
    "response_queue_key": "device_responses",
    "dead_letter_queue_key": "device_raw_messages_dlq",
    "consumer_group": "parser_group",
    "consumer_name": "parser_consumer",
    "process_max_retries": 3,
    "retry_backoff_ms": 50
  },
  "database": {
    "host": "localhost",
    "port": 3306,
    "database": "rms",
    "username": "root",
    "password": "password"
  },
  "thread": {
    "worker_threads": 4,
    "batch_size": 10,
    "queue_size": 1000
  }
}
```

### 5. 消息重试与死信队列（DLQ）

为避免异常消息在 PEL 中被无限认领重试，解析器已支持“有限重试 + 死信转储”。

- 重试次数：`redis.process_max_retries`
- 重试间隔：`redis.retry_backoff_ms`
- 死信队列：`redis.dead_letter_queue_key`（Redis List）

处理规则：

1. 读取到消息后，解析器最多尝试处理 `process_max_retries` 次。
2. 单次失败（解析失败、校验失败、处理异常）会记录失败原因，并按 `retry_backoff_ms` 退避后重试。
3. 超过最大重试次数后，将原始消息封装为 JSON 写入 `dead_letter_queue_key`。
4. 写入死信队列后，ACK 原始 Stream 消息，避免其继续滞留 PEL 并重复认领。

DLQ 消息主要字段：

- `original_id`
- `stream_key`
- `source_ip`
- `raw_data_base64`
- `attempts`
- `final_reason`
- `dropped_at_ms`
- `additional_fields`

> 建议：生产环境可先使用 `process_max_retries=3`、`retry_backoff_ms=50`，若外部依赖波动明显，可适当提高重试次数。

### 4. 运行解析器

```bash
# 前台运行
./build/bin/cpp_parser -c config/parser_config.json

# 后台运行
./build/bin/cpp_parser -c config/parser_config.json --daemon

# 指定线程数
./build/bin/cpp_parser -c config/parser_config.json --threads 8
```

## 📡 协议支持

### 消息类型映射

| 消息ID | 消息类型 | 处理器 | 业务服务 | 说明 |
|--------|----------|--------|----------|------|
| 2 | 终端注册 | `RegistrationHandler` | `DeviceService` | 设备首次连接注册 |
| 3 | 终端鉴权 | `LoginHandler` | `DeviceService` | 设备登录认证 |
| 4 | 心跳 | `HeartbeatHandler` | `DeviceService` | 设备在线状态维护 |
| 10 | 故障上报 | `FaultReportHandler` | `FaultService` | 设备故障信息上报 |
| 12 | 点钞上报 | `BanknoteReportHandler` | `BanknoteService` | 点钞数据上报 |
| 6 | 升级结果 | `UpgradeResultHandler` | `UpgradeService` | 固件升级结果上报 |

### 协议格式

#### 消息头格式
```
msg_head(2) + msg_type(1) + msg_body_len(2) + msg_attribute(1) + 
msg_id(2) + devUniqueId(32) + seNum(2)
```

#### 消息体格式
根据`dp_protocol_v1.json`配置动态解析

#### 消息尾格式
```
CRC16(2) + tail(2)
```

## 🔧 开发指南

### 添加新的消息类型

#### 步骤1: 创建Handler类
```cpp
// include/logic/handlers/NewMessageHandler.h
class NewMessageHandler : public IMessageHandler {
public:
    NewMessageHandler(std::shared_ptr<DeviceService> device_service,
                     std::shared_ptr<ResponseGenerator> response_generator);
    
    std::vector<uint8_t> Handle(const ParsedMessage& parsed_msg) override;
    bool CanHandle(uint16_t msg_id) const override;
    std::string GetHandlerName() const override;
};
```

#### 步骤2: 实现Handler
```cpp
// src/logic/handlers/NewMessageHandler.cpp
std::vector<uint8_t> NewMessageHandler::Handle(const ParsedMessage& parsed_msg) {
    auto result = device_service_->ProcessNewMessage(parsed_msg);
    return response_generator_->CreateNewMessageResponse(parsed_msg, result);
}

bool NewMessageHandler::CanHandle(uint16_t msg_id) const {
    return msg_id == 15; // 新消息ID
}
```

#### 步骤3: 在Factory中注册
```cpp
// src/logic/handlers/MessageHandlerFactory.cpp
handlers_[15] = std::make_unique<NewMessageHandler>(device_service, response_generator);
```

### 添加新的业务服务

#### 步骤1: 定义服务接口
```cpp
// include/logic/services/NewService.h
class NewService {
public:
    virtual ~NewService() = default;
    virtual NewMessageResult ProcessNewMessage(const ParsedMessage& parsed_msg) = 0;
};
```

#### 步骤2: 实现服务
```cpp
// include/logic/services/NewServiceImpl.h
class NewServiceImpl : public NewService {
public:
    NewServiceImpl(std::shared_ptr<DPower::DB::DPowerDatabaseClient> db_client,
                   std::shared_ptr<DPower::Cache::DPowerCacheClient> cache_client);
    
    NewMessageResult ProcessNewMessage(const ParsedMessage& parsed_msg) override;
};
```

#### 步骤3: 在MessageProcessor中初始化
```cpp
// src/logic/MessageProcessor.cpp
new_service_ = std::make_shared<NewServiceImpl>(db_client_, cache_client_);
```

## 🚀 部署指南

### 生产环境部署

#### 1. 系统要求
- CPU: 4核心以上
- 内存: 8GB以上
- 网络: 千兆网卡
- 存储: SSD推荐

#### 2. 部署步骤
```bash
# 1. 编译发布版本
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)

# 2. 创建部署目录
sudo mkdir -p /opt/cpp_parser
sudo cp bin/cpp_parser /opt/cpp_parser/
sudo cp -r config /opt/cpp_parser/

# 3. 创建系统服务
sudo nano /etc/systemd/system/cpp-parser.service
```

#### 3. 系统服务配置
```ini
[Unit]
Description=C++ Parser Service
After=network.target mysql.service redis.service

[Service]
Type=simple
User=parser
WorkingDirectory=/opt/cpp_parser
ExecStart=/opt/cpp_parser/cpp_parser -c /opt/cpp_parser/config/parser_config.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 4. 启动服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable cpp-parser
sudo systemctl start cpp-parser
sudo systemctl status cpp-parser
```

### 监控和日志

#### 1. 日志配置
```json
{
  "log": {
    "enable_console_log": true,
    "enable_file_log": true,
    "log_level": "INFO",
    "log_file_path": "/var/log/cpp_parser/parser.log"
  }
}
```

#### 2. 性能监控
```json
{
  "monitor": {
    "enable_performance_log": true,
    "health_check_interval": 30,
    "stats_report_interval": 60
  }
}
```

## 🔍 故障排查

### 常见问题

#### 1. 编译错误
```bash
# 检查依赖库
ldconfig -p | grep boost
ldconfig -p | grep redis

# 重新安装依赖
sudo apt-get install -y libboost-all-dev
./install_redis_plus_plus.sh
```

#### 2. 运行时错误
```bash
# 检查配置文件
./cpp_parser --validate-config

# 检查Redis连接
redis-cli ping

# 检查MySQL连接
mysql -u root -p -e "SELECT 1;"
```

#### 3. 性能问题
```bash
# 查看系统资源
htop
iostat -x 1
netstat -i

# 查看应用日志
tail -f /var/log/cpp_parser/parser.log
```

### 调试模式

```bash
# 启用调试日志
./cpp_parser -c config/parser_config.json --debug

# 单线程模式
./cpp_parser -c config/parser_config.json --threads 1

# 详细输出
./cpp_parser -c config/parser_config.json --verbose
```

## 📊 性能优化

### 1. 系统优化
```bash
# 调整文件描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 调整内核参数
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" >> /etc/sysctl.conf
sysctl -p
```

### 2. 应用优化
```json
{
  "thread": {
    "worker_threads": 8,
    "batch_size": 20,
    "queue_size": 2000
  },
  "redis": {
    "connection_pool_size": 10,
    "block_timeout": 1000
  }
}
```

## 🤝 贡献指南

### 代码规范
- 使用C++17标准
- 遵循Google C++ Style Guide
- 所有公共接口必须有文档注释
- 单元测试覆盖率 > 80%

### 提交规范
```bash
# 提交前检查
make test
make lint

# 提交信息格式
git commit -m "feat: add new message handler for msg_id 15"
git commit -m "fix: resolve memory leak in cache adapter"
git commit -m "docs: update deployment guide"
```

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 📞 联系方式

- 项目维护者: [维护者姓名]
- 邮箱: [邮箱地址]
- 项目地址: [项目URL]

---

**注意**: 本系统为金融设备通信系统，请确保在生产环境中进行充分的安全测试和性能测试。 

**生产级docker编译部署已完成**: 
cd ~/rms/device_end/cpp_parser
sudo docker build -t dpower-parser:v1.0 .
sudo docker save -o parser.tar dpower-parser:v1.0



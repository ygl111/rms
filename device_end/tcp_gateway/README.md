# TCP Gateway

一个高性能的 TCP 网关服务，用于接收设备数据并转发到 Redis Stream。

## 功能特性

- 🔄 **异步 I/O**: 基于 Boost.Asio 的高性能异步网络处理
- 🏗️ **DPower 架构**: 使用抽象接口，便于替换底层实现
- 📡 **Redis 集成**: 支持 Redis Stream 和 List 操作
- 🔧 **可配置**: 支持配置文件自定义端口和 Redis 设置
- 🚀 **高性能**: 多线程处理，支持高并发连接
- 📊 **监控**: 内置健康检查和统计功能

## 系统要求

- **操作系统**: Ubuntu 18.04+ / Debian 9+
- **C++ 标准**: C++17
- **CMake**: >= 3.10
- **Boost**: >= 1.82.0
- **Redis**: 最新版本

## 快速部署

### 方法一：使用自动部署脚本（推荐）

```bash
# 1. 克隆项目
git clone <repository-url>
cd tcp_gateway

# 2. 运行部署脚本
./deploy.sh
```

部署脚本会自动：
- 安装所有系统依赖
- 编译项目
- 安装并配置 Redis
- 创建 systemd 服务
- 启动服务

### 方法二：手动部署

#### 1. 安装依赖

```bash
# 更新包列表
sudo apt update

# 安装编译工具
sudo apt install -y build-essential cmake pkg-config

# 安装 Boost 库
sudo apt install -y libboost-system-dev libboost-thread-dev

# 安装 Redis 客户端库
sudo apt install -y libredis++-dev libhiredis-dev

# 安装其他依赖
sudo apt install -y libpthread-stubs0-dev libnlohmann-json3-dev
```

#### 2. 安装 Redis 服务器

```bash
sudo apt install -y redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### 3. 编译项目

```bash
mkdir -p build && cd build
cmake ..
make -j$(nproc)
cd ..
```

#### 4. 配置和运行

```bash
# 检查配置文件
cat config/gateway.conf

# 运行程序
./build/gateway
```

## 配置文件

配置文件位于 `config/gateway.conf`：

```ini
[Server]
# 网关服务监听的TCP端口
listen_port = 12345

[Redis]
# Redis服务器地址
host = 127.0.0.1
port = 6379

# Redis Stream 键名（用于接收设备数据）
request_stream_key = device_raw_messages

# Redis List 键名（用于发送响应）
response_queue_key = device_responses
```

## 服务管理

### 使用 systemd 管理服务

```bash
# 启动服务
sudo systemctl start tcp-gateway

# 停止服务
sudo systemctl stop tcp-gateway

# 重启服务
sudo systemctl restart tcp-gateway

# 查看状态
sudo systemctl status tcp-gateway

# 查看日志
sudo journalctl -u tcp-gateway -f

# 启用开机自启
sudo systemctl enable tcp-gateway
```

### 手动运行

```bash
# 前台运行
./build/gateway

# 后台运行
nohup ./build/gateway > gateway.log 2>&1 &
```

## 监控和调试

### 检查服务状态

```bash
# 检查端口监听
netstat -tuln | grep 12345

# 检查 Redis 连接
redis-cli ping

# 检查 Redis Stream
redis-cli XINFO STREAM device_raw_messages
```

### 查看日志

```bash
# systemd 日志
sudo journalctl -u tcp-gateway -f

# 手动运行的日志
tail -f gateway.log
```

### 性能监控

```bash
# 查看进程状态
ps aux | grep gateway

# 查看网络连接
ss -tuln | grep 12345

# 查看 Redis 统计
redis-cli info memory
```

## 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 检查端口占用
   sudo lsof -i :12345
   
   # 杀死占用进程
   sudo kill -9 <PID>
   ```

2. **Redis 连接失败**
   ```bash
   # 检查 Redis 状态
   sudo systemctl status redis-server
   
   # 重启 Redis
   sudo systemctl restart redis-server
   ```

3. **编译失败**
   ```bash
   # 清理构建目录
   rm -rf build
   
   # 重新编译
   mkdir build && cd build
   cmake ..
   make
   ```

4. **权限问题**
   ```bash
   # 确保用户有执行权限
   chmod +x build/gateway
   
   # 检查配置文件权限
   ls -la config/gateway.conf
   ```

### 调试模式

```bash
# 使用 gdb 调试
gdb build/gateway

# 使用 valgrind 检查内存
valgrind --leak-check=full ./build/gateway
```

## 架构说明

### 组件结构

```
tcp_gateway/
├── include/
│   ├── logic/           # 业务逻辑头文件
│   └── dpower/          # DPower 抽象接口
├── src/
│   ├── app/             # 应用程序入口
│   ├── logic/           # 业务逻辑实现
│   └── adapters/        # 适配器实现
├── config/              # 配置文件
├── build/               # 构建输出
└── external/            # 外部依赖
```

### 数据流

```
设备 -> TCP Gateway -> Redis Stream -> C++ Parser -> 数据库
                ↓
            Redis List -> TCP Gateway -> 设备
```

## 开发指南

### 添加新功能

1. 在 `include/logic/` 中添加头文件
2. 在 `src/logic/` 中实现功能
3. 更新 CMakeLists.txt
4. 重新编译

### 替换底层实现

项目使用 DPower 架构，可以轻松替换底层实现：

- **网络库**: 替换 Boost.Asio 适配器
- **Redis 客户端**: 替换 redis++ 适配器
- **JSON 库**: 替换 nlohmann/json 适配器

## 许可证

[许可证信息]

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

[联系信息] 

**生产级docker编译部署已完成**: 
cd ~/rms/device_end/tcp_gateway
sudo docker build -t dpower-gateway:v1.0 .
sudo docker save -o gateway.tar dpower-gateway:v1.0
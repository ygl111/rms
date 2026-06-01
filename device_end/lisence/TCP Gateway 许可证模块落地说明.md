# TCP Gateway 许可证模块落地说明

## 1. 背景与目标

本次改造目标是为 TCP Gateway 增加许可证控制能力，且遵循以下业务边界：

- 仅限制设备连接与通信链路。
- 不影响后台 Web 登录与历史数据查询能力。
- 采用 fail-close 策略：许可证无效、过期或 MAC 不匹配时，拒绝新连接，并按策略断开现有连接。

## 2. 改造范围与最终状态

### 2.1 核心代码改造

- 新增许可证判定模块：
  - [device_end/tcp_gateway/include/logic/LicenseGuard.h](include/logic/LicenseGuard.h)
  - [device_end/tcp_gateway/src/logic/LicenseGuard.cpp](src/logic/LicenseGuard.cpp)
- 接入连接入口与 watchdog：
  - [device_end/tcp_gateway/include/logic/TCPServer.h](include/logic/TCPServer.h)
  - [device_end/tcp_gateway/src/logic/TCPServer.cpp](src/logic/TCPServer.cpp)
- 支持会话计数与批量断开：
  - [device_end/tcp_gateway/include/logic/SessionManager.h](include/logic/SessionManager.h)
  - [device_end/tcp_gateway/src/logic/SessionManager.cpp](src/logic/SessionManager.cpp)
- 支持单会话强制关闭：
  - [device_end/tcp_gateway/include/logic/TCPSession.h](include/logic/TCPSession.h)
  - [device_end/tcp_gateway/src/logic/TCPSession.cpp](src/logic/TCPSession.cpp)

### 2.2 构建与配置改造

- CMake 增加许可证源文件与 OpenSSL 链接：
  - [device_end/tcp_gateway/CMakeLists.txt](CMakeLists.txt)
- 增加许可证模板文件：
  - [device_end/tcp_gateway/config/license.env.example](config/license.env.example)
- 实际运行许可证文件（运行态，不建议入库）：
  - [device_end/tcp_gateway/config/license.env](config/license.env)
- Git 忽略策略：
  - [.gitignore](../../.gitignore)

### 2.3 工具脚本

- 签发许可证脚本：
  - [device_end/tcp_gateway/tools/issue_license.sh](tools/issue_license.sh)

## 3. 许可证模型与字段

许可证 token 采用以下结构：

- payload：JSON，包含三字段
  - exp：过期时间戳（Unix 秒，UTC 基准）
  - max_devices：最大并发连接数
  - mac：绑定服务器 MAC
- signature：payload 的 RSA-PSS-SHA256 签名
- token 格式：base64url(payload).base64url(signature)

## 4. 运行时行为

### 4.1 判定时机

- 新连接进入时判定一次。
- watchdog 线程每秒判定一次。

### 4.2 判定结果行为

- ok：允许连接。
- over_limit：拒绝新连接，已连设备保留。
- license_expired / license_invalid / license_mac_mismatch：
  - 拒绝新连接。
  - 触发断开现有连接。

## 5. 发证与部署流程

### 5.1 推荐发证命令（UTC 时间输入）

在 Linux 发证环境执行：

```bash
cd device_end/tcp_gateway/tools
bash issue_license.sh \
  --mac b8:2a:72:d2:3c:f0 \
  --exp-utc "2026-12-31 23:59:59" \
  --max 30 \
  --priv ./vendor_private.pem \
  --outdir ./out
```

或者

```bash
bash issue_license.sh --mac b8:2a:72:d2:3c:f0 --exp-utc "2026-04-18 07:20:00" --max 30 --priv /home/rsb/license_vendor/vendor_private.pem --outdir /home/rsb/license_vendor/out
```

说明：
- 输入时间为UTC时间，格式为 "YYYY-MM-DD HH:MM:SS"，单位数需注意补零。脚本会把 UTC 时间自动转换为 Unix 时间戳。
- 产物在 out 目录：payload.json、payload.sig、license.token。

### 5.2 网关侧生效步骤

1. 将 license.token 的整行内容写入 [device_end/tcp_gateway/config/license.env](config/license.env) 的 LICENSE_TOKEN。
2. 重启 gateway 进程。

注意：当前实现不是热重载，更新 token 后必须重启进程才会生效。

## 6. 时间戳与时区说明

- exp 为 UTC 秒级时间戳。
- 判定逻辑按服务器当前系统时间转换后的 Unix 秒进行比较。
- 若日志出现 license_expired，先核对：
  1. token 中 exp 对应时间。
  2. 服务器当前 UTC 时间。

## 7. 网卡绑定说明

### 7.1 为什么会出现 MAC 不匹配

在多网卡、虚拟网卡或网卡状态变化场景下，程序实际取到的网卡可能与人工查询网卡不一致。

### 7.2 建议的确定方法

在目标服务器执行：

```bash
ip route get 183.169.121.226
```

从输出里取 dev 网卡名，再执行：

```bash
cat /sys/class/net/<网卡名>/address
```

将该地址作为发证 mac 字段。

## 8. 常见问题与处理

### 8.1 原因：license_mac_mismatch

现象：日志反复出现 reason=license_mac_mismatch。

处理：

1. 核对程序实际 machine_mac。
2. 按实际绑定网卡重新签发 token。
3. 替换 token 并重启 gateway。

### 8.2 原因：license_expired

现象：日志反复出现 reason=license_expired。

处理：

1. 重新签发未来有效期 token。
2. 更新 [device_end/tcp_gateway/config/license.env](config/license.env)。
3. 重启 gateway。

## 9. 性能影响评估（当前实现）

- 对已建立连接的数据吞吐影响较小。
- 对高频新建连接场景有额外开销（验签与解析）。
- watchdog 每秒判定有固定开销。
- 异常状态下日志刷屏会放大开销。

建议：生产环境保持日志级别与日志量可控，避免异常状态长期刷屏。

## 11. 后续可选优化（本次未启用）

- license 文件变更检测与受控重载。
- 判定结果短周期缓存，降低高频验签成本。
- 更精细的日志节流策略。

当前阶段维持“重启生效”方案，简单、可控、风险低。

#!/bin/bash

# TCP网关配置文件验证脚本
# 用于检查gateway.conf文件的语法和配置项

CONFIG_FILE="gateway.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="$SCRIPT_DIR/$CONFIG_FILE"

echo "=== TCP Gateway 配置文件验证 ==="
echo "配置文件路径: $CONFIG_PATH"
echo ""

# 检查文件是否存在
if [ ! -f "$CONFIG_PATH" ]; then
    echo "❌ 错误: 配置文件不存在: $CONFIG_PATH"
    exit 1
fi

echo "✅ 配置文件存在"

# 检查文件权限
if [ ! -r "$CONFIG_PATH" ]; then
    echo "❌ 错误: 配置文件不可读"
    exit 1
fi

echo "✅ 配置文件可读"

# 检查基本语法
echo ""
echo "=== 语法检查 ==="

# 检查是否有未闭合的节
unclosed_sections=$(grep -c "^\[.*$" "$CONFIG_PATH")
closed_sections=$(grep -c "^\[.*\]$" "$CONFIG_PATH")

if [ "$unclosed_sections" -ne "$closed_sections" ]; then
    echo "❌ 警告: 可能存在未正确闭合的配置节"
else
    echo "✅ 配置节语法正确"
fi

# 检查必要的配置项
echo ""
echo "=== 必要配置项检查 ==="

# 检查Redis配置
if grep -q "^host = " "$CONFIG_PATH"; then
    redis_host=$(grep "^host = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ Redis主机: $redis_host"
else
    echo "❌ 缺少Redis主机配置"
fi

if grep -q "^port = " "$CONFIG_PATH"; then
    redis_port=$(grep "^port = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ Redis端口: $redis_port"
else
    echo "❌ 缺少Redis端口配置"
fi

if grep -q "^request_stream_key = " "$CONFIG_PATH"; then
    stream_key=$(grep "^request_stream_key = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 请求流键: $stream_key"
else
    echo "❌ 缺少请求流键配置"
fi

if grep -q "^response_queue_key = " "$CONFIG_PATH"; then
    queue_key=$(grep "^response_queue_key = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 响应队列键: $queue_key"
else
    echo "❌ 缺少响应队列键配置"
fi

# 检查端口配置
echo ""
echo "=== 端口配置检查 ==="

if grep -q "^listen_ports = " "$CONFIG_PATH"; then
    ports=$(grep "^listen_ports = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 监听端口: $ports"
    
    # 解析端口列表
    IFS=',' read -ra PORT_ARRAY <<< "$ports"
    for port_item in "${PORT_ARRAY[@]}"; do
        port_item=$(echo "$port_item" | tr -d ' ')
        if [[ $port_item == *":"* ]]; then
            port_num=$(echo "$port_item" | cut -d':' -f1)
            protocol=$(echo "$port_item" | cut -d':' -f2)
            echo "   - 端口 $port_num: $protocol"
        else
            echo "   - 端口 $port_item: 默认协议"
        fi
    done
else
    echo "⚠️  未配置监听端口，将使用默认端口"
fi

# 检查协议配置
echo ""
echo "=== 协议配置检查 ==="

if grep -q "^registry_file = " "$CONFIG_PATH"; then
    registry_file=$(grep "^registry_file = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 协议注册文件: $registry_file"
    
    # 检查协议注册文件是否存在
    if [ -f "$SCRIPT_DIR/$registry_file" ]; then
        echo "✅ 协议注册文件存在"
    else
        echo "❌ 协议注册文件不存在: $SCRIPT_DIR/$registry_file"
    fi
else
    echo "❌ 缺少协议注册文件配置"
fi

# 检查性能配置
echo ""
echo "=== 性能配置检查 ==="

if grep -q "^max_connections = " "$CONFIG_PATH"; then
    max_conn=$(grep "^max_connections = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 最大连接数: $max_conn"
else
    echo "⚠️  未配置最大连接数，使用默认值"
fi

if grep -q "^worker_threads = " "$CONFIG_PATH"; then
    worker_threads=$(grep "^worker_threads = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    if [ "$worker_threads" -eq 0 ]; then
        echo "✅ 工作线程数: 自动（CPU核心数）"
    else
        echo "✅ 工作线程数: $worker_threads"
    fi
else
    echo "⚠️  未配置工作线程数，使用默认值"
fi

# 检查日志配置
echo ""
echo "=== 日志配置检查 ==="

if grep -q "^log_level = " "$CONFIG_PATH"; then
    log_level=$(grep "^log_level = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 日志级别: $log_level"
else
    echo "⚠️  未配置日志级别，使用默认值"
fi

if grep -q "^enable_console_log = " "$CONFIG_PATH"; then
    console_log=$(grep "^enable_console_log = " "$CONFIG_PATH" | cut -d'=' -f2 | tr -d ' ')
    echo "✅ 控制台日志: $console_log"
else
    echo "⚠️  未配置控制台日志，使用默认值"
fi

# 总结
echo ""
echo "=== 验证总结 ==="
echo "配置文件验证完成！"
echo ""
echo "如果看到 ❌ 错误，请修复相应的配置项"
echo "如果看到 ⚠️  警告，表示使用默认值，通常可以接受"
echo "如果看到 ✅ 成功，表示配置项正确"
echo ""
echo "建议在启动网关前运行此验证脚本确保配置正确。" 
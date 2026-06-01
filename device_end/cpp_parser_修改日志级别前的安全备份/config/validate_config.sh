#!/bin/bash

# 配置验证脚本
echo "=== C++ Parser 配置验证 ==="

# 检查配置文件是否存在
if [ ! -f "config/parser_config.json" ]; then
    echo "❌ 配置文件不存在: config/parser_config.json"
    exit 1
fi

echo "✅ 配置文件存在"

# 检查JSON格式是否正确
if ! jq empty config/parser_config.json 2>/dev/null; then
    echo "❌ 配置文件JSON格式错误"
    exit 1
fi

echo "✅ JSON格式正确"

# 提取并显示关键配置
echo ""
echo "=== 当前配置 ==="

# Redis配置
echo "Redis配置:"
redis_host=$(jq -r '.redis.host' config/parser_config.json)
redis_port=$(jq -r '.redis.port' config/parser_config.json)
redis_db=$(jq -r '.redis.db' config/parser_config.json)
echo "  Host: $redis_host"
echo "  Port: $redis_port"
echo "  Database: $redis_db"

# 数据库配置
echo ""
echo "数据库配置:"
db_uri=$(jq -r '.database.uri' config/parser_config.json)
db_user=$(jq -r '.database.user' config/parser_config.json)
echo "  URI: $db_uri"
echo "  User: $db_user"

# FTP配置
echo ""
echo "FTP配置:"
ftp_host=$(jq -r '.ftp.host' config/parser_config.json)
ftp_port=$(jq -r '.ftp.port' config/parser_config.json)
ftp_user=$(jq -r '.ftp.user' config/parser_config.json)
echo "  Host: $ftp_host"
echo "  Port: $ftp_port"
echo "  User: $ftp_user"

# 验证Redis连接
echo ""
echo "=== 连接测试 ==="

# 测试Redis连接
if redis-cli -h "$redis_host" -p "$redis_port" ping >/dev/null 2>&1; then
    echo "✅ Redis连接成功"
else
    echo "❌ Redis连接失败"
fi

# 测试数据库连接（需要mysql客户端）
if command -v mysql >/dev/null 2>&1; then
    # 从URI中提取主机和端口
    db_host=$(echo "$db_uri" | cut -d: -f1)
    db_port=$(echo "$db_uri" | cut -d: -f2 | cut -d/ -f1)
    db_name=$(echo "$db_uri" | cut -d/ -f2)
    
    if mysql -h "$db_host" -P "$db_port" -u "$db_user" -p"$(jq -r '.database.password' config/parser_config.json)" -e "SELECT 1;" >/dev/null 2>&1; then
        echo "✅ 数据库连接成功"
    else
        echo "❌ 数据库连接失败"
    fi
else
    echo "⚠️  mysql客户端未安装，跳过数据库连接测试"
fi

echo ""
echo "=== 配置验证完成 ===" 
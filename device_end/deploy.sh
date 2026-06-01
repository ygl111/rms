#!/bin/bash
set -euo pipefail

echo "=========================================="
echo "统一部署脚本：cpp_parser + tcp_gateway"
echo "=========================================="

# 1. 安装系统依赖
sudo apt update
sudo apt install -y \
    build-essential \
    g++ \
    cmake \
    make \
    pkg-config \
    git \
    curl \
    wget \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-filesystem-dev \
    libspdlog-dev \
    libhiredis-dev \
    librabbitmq-dev \
    libpthread-stubs0-dev \
    libssl-dev \
    redis-server \
    redis-tools \
    mysql-server \
    libmysqlclient-dev \
    libmysqlcppconn-dev \
    gdb valgrind linux-tools-common linux-tools-$(uname -r) net-tools iproute2

# 2. 检查并安装 redis++（redis-plus-plus）
if ! pkg-config --exists redis++ 2>/dev/null; then
    echo "[INFO] 未检测到 redis++，检查本地源码..."
    
    # 检查当前目录是否存在指定版本的源码文件夹
    REDIS_PLUS_PLUS_DIR="redis-plus-plus-1.3.14"
    if [ ! -d "$REDIS_PLUS_PLUS_DIR" ]; then
        echo "[ERROR] 未找到 $REDIS_PLUS_PLUS_DIR 源码文件夹！"
        echo "[ERROR] 请确保在当前目录下存在 $REDIS_PLUS_PLUS_DIR 文件夹"
        echo "[ERROR] 不允许自动下载，仅支持本地源码编译安装"
        exit 1
    fi
    
    echo "[INFO] 找到本地源码 $REDIS_PLUS_PLUS_DIR，开始编译安装..."
    cd "$REDIS_PLUS_PLUS_DIR"
    mkdir -p build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    sudo make install
    sudo ldconfig
    cd ../..
    echo "[INFO] redis++ 从本地源码安装完成。"
else
    echo "[INFO] redis++ 已安装，版本: $(pkg-config --modversion redis++)"
fi

# 3. 编译 cpp_parser 项目
CPP_PARSER_DIR="cpp_parser"
if [ -d "$CPP_PARSER_DIR" ]; then
    cd "$CPP_PARSER_DIR"
    mkdir -p build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    cd ../..
else
    echo "未找到 cpp_parser 目录。"
    exit 1
fi

# 4. 编译 tcp_gateway 项目
TCP_GATEWAY_DIR="tcp_gateway"
if [ -d "$TCP_GATEWAY_DIR" ]; then
    cd "$TCP_GATEWAY_DIR"
    mkdir -p build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    cd ../..
else
    echo "未找到 tcp_gateway 目录。"
    exit 1
fi

# 5. 启动 redis-server（如有需要）
echo "如需启动 redis-server，请运行：sudo systemctl start redis-server"

# 6. 启动 mysql-server（如有需要）
echo "如需启动 mysql-server，请运行：sudo systemctl start mysql"

# 7. 启动项目前先清理残留 cpp_parser 实例（如需）
CPP_PARSER_BIN="cpp_parser/build/bin/cpp_parser"
if [ -x "$CPP_PARSER_BIN" ]; then
    PROCESS_KEY="cpp_parser -c config/parser_config.json --threads 1"
    START_CMD="cd cpp_parser && DP_DB_PER_THREAD=1 DP_DB_DEBUG=0 ./build/bin/cpp_parser -c config/parser_config.json --threads 1 &"

    if pgrep -f "$PROCESS_KEY" > /dev/null; then
        OLD_PIDS=$(pgrep -f "$PROCESS_KEY" | tr '\n' ' ')
        echo "检测到运行中的 cpp_parser 进程：$OLD_PIDS"
        echo "正在终止旧进程以避免多实例干扰..."
        pkill -TERM -f "$PROCESS_KEY" || true

        # 最多等待 15 秒优雅退出，超时后强制回收。
        WAIT_SECONDS=15
        ELAPSED=0
        while pgrep -f "$PROCESS_KEY" > /dev/null && [ "$ELAPSED" -lt "$WAIT_SECONDS" ]; do
            sleep 1
            ELAPSED=$((ELAPSED + 1))
        done

        if pgrep -f "$PROCESS_KEY" > /dev/null; then
            echo "旧进程在 ${WAIT_SECONDS}s 内未退出，执行强制终止..."
            pkill -KILL -f "$PROCESS_KEY" || true
        fi
    fi

    echo "启动 cpp_parser..."
    eval "$START_CMD"
else
    echo "未找到可执行文件 $CPP_PARSER_BIN，暂不自动启动 cpp_parser。"
fi

# 8. 运行 tcp_gateway 可执行文件（示例）
echo "tcp_gateway 可执行文件路径：tcp_gateway/build/gateway"
echo "如需启动请运行：cd tcp_gateway && ./build/gateway &"

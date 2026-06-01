# =======================================================
# Stage 1: 构建阶段 (Builder) - 包含全部编译工具和源码
# =======================================================
FROM ubuntu:20.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# 1. 安装基础编译工具和 Boost、OpenSSL 依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libssl-dev \
    libboost-system-dev \
    libboost-thread-dev \
    libspdlog-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 把本地下载好的源码压缩包拷贝到容器里
COPY hiredis.tar.gz /tmp/
COPY redis-plus-plus.tar.gz /tmp/

# 3. 解压并编译 hiredis
RUN cd /tmp && tar -xzf hiredis.tar.gz \
    && cd hiredis-1.0.2 && make && make install

# 4. 解压并编译 redis-plus-plus
RUN cd /tmp && tar -xzf redis-plus-plus.tar.gz \
    && cd redis-plus-plus-1.3.5 && mkdir build && cd build \
    && cmake -DREDIS_PLUS_PLUS_CXX_STANDARD=17 .. \
    && make -j$(nproc) && make install

# 5. 拷贝网关源码并编译 (Release 模式，自动触发 -s 剥离符号)
WORKDIR /app
COPY . .
RUN mkdir -p build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && make -j$(nproc)

# =======================================================
# Stage 2: 运行阶段 (Runtime) - 极其干净的黑盒环境
# =======================================================
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. 仅安装运行时的动态库依赖 
RUN apt-get update && apt-get install -y \
    libssl1.1 \
    libboost-system1.71.0 \
    libboost-thread1.71.0 \
    libspdlog1 \
    && rm -rf /var/lib/apt/lists/*

# 2. 从 Builder 拷贝我们自己编译的 redis++ 和 hiredis 动态库
COPY --from=builder /usr/local/lib/libhiredis* /usr/local/lib/
COPY --from=builder /usr/local/lib/libredis++* /usr/local/lib/
# 刷新动态链接库缓存
RUN ldconfig

WORKDIR /app

# 3. 剥离源码，仅拷贝可执行文件和配置文件
COPY --from=builder /app/build/gateway ./bin/gateway
COPY --from=builder /app/config ./config
RUN mkdir -p /app/logs

# 4. 启动网关
CMD ["./bin/gateway"]
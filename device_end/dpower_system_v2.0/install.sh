#!/bin/bash
echo "1. 导入离线镜像..."
docker load -i images/gateway.tar
docker load -i images/parser.tar

echo "2. 启动 DPower 工业接入系统..."
docker compose up -d

echo "系统已启动！运行 docker-compose logs -f 查看日志。"
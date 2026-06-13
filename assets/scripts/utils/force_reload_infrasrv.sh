#!/bin/bash

# 强制重启 infrasrv 并清理旧配置
# 用于解决配置更新不生效的问题

set -e

echo "========================================="
echo "强制重建 infrasrv"
echo "========================================="

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 检测容器引擎
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 未找到 docker-compose 或 podman-compose"
    exit 1
fi

echo "1. 停止 infrasrv..."
$COMPOSE_CMD -f docker-compose.infra.yml stop infrasrv.service || true

echo "2. 删除 infrasrv 容器..."
if command -v podman &> /dev/null; then
    podman rm -f my_app_infrasrv || true
else
    docker rm -f my_app_infrasrv || true
fi

echo "3. 重建并启动 infrasrv..."
$COMPOSE_CMD -f docker-compose.infra.yml up -d --build infrasrv.service

echo "4. 等待服务启动..."
sleep 5

echo "5. 验证连接配置..."
# 检查日志中是否正确连接到 controllersrv
if command -v podman &> /dev/null; then
    podman logs my_app_infrasrv | grep "ControllerSrvApi initialized"
else
    docker logs my_app_infrasrv | grep "ControllerSrvApi initialized"
fi

echo ""
echo "✅ infrasrv 已重建"
echo "请再次尝试 opsbffsrv 的服务管理操作"

#!/bin/bash

# Docker Compose 重建脚本
# 用于重建并重启 Docker Compose 集群或单个服务
# 用法: ./rebuild_compose.sh [service_name]

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "重建 Docker Compose 集群"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

# 检查 docker-compose.yml 是否存在
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 未找到 docker-compose.yml 文件"
    exit 1
fi

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "正在重建服务: $SERVICE_NAME"
    echo ""
    docker-compose up -d --build "$SERVICE_NAME"
else
    echo "正在重建所有服务..."
    echo ""
    docker-compose up -d --build
fi

# 等待服务启动
echo ""
echo "等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "========================================="
echo "服务状态检查"
echo "========================================="
docker-compose ps

echo ""
echo "✅ Docker Compose 重建完成"

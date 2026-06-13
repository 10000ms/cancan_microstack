#!/bin/bash

# Docker Compose 强制重建脚本
# 用于强制重新构建 Docker 镜像（不使用缓存）
# "把之前的干掉，然后在重新 build"
# 用法: ./force_rebuild_images.sh [service_name]

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "强制重建 Docker 镜像 (无缓存)"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "正在强制重建服务镜像: $SERVICE_NAME"
    echo ""
    docker-compose build --no-cache "$SERVICE_NAME"
else
    echo "正在强制重建所有服务镜像..."
    echo ""
    docker-compose build --no-cache
fi

echo ""
echo "✅ 强制构建完成"

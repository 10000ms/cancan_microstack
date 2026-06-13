#!/bin/bash

# Docker Compose 构建脚本
# 用于构建 Docker 镜像（利用缓存，增量构建）
# "如果有，就不build，没有的image才build（或 download）" -> Docker build 的默认行为利用缓存
# 用法: ./build_images.sh [service_name]

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "构建 Docker 镜像 (增量/缓存)"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行"
    exit 1
fi

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "正在构建服务镜像: $SERVICE_NAME"
    echo ""
    docker-compose build "$SERVICE_NAME"
else
    echo "正在构建所有服务镜像..."
    echo ""
    docker-compose build
fi

echo ""
echo "✅ 构建完成"

#!/bin/bash

# Podman Compose 构建脚本
# 用于构建 Podman 镜像（利用缓存，增量构建）
# 用法: ./build_images_podman.sh [service_name]

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "构建 Podman 镜像 (增量/缓存)"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检测 Podman Compose 命令
COMPOSE_CMD=""
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
elif podman compose version > /dev/null 2>&1; then
    COMPOSE_CMD="podman compose"
else
    echo "❌ 未找到 Podman Compose 命令"
    exit 1
fi

echo "使用命令: $COMPOSE_CMD"
echo ""

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "正在构建服务镜像: $SERVICE_NAME"
    echo ""
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose build "$SERVICE_NAME"
    else
        podman compose build "$SERVICE_NAME"
    fi
else
    echo "正在构建所有服务镜像..."
    echo ""
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose build
    else
        podman compose build
    fi
fi

echo ""
echo "✅ 构建完成"

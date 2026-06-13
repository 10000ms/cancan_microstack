#!/bin/bash

# Podman Compose 强制重建脚本
# 用于强制重新构建 Podman 镜像（不使用缓存）
# 用法: ./force_rebuild_images_podman.sh [service_name]

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "强制重建 Podman 镜像 (无缓存)"
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

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "正在强制重建服务镜像: $SERVICE_NAME"
    echo ""
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose build --no-cache "$SERVICE_NAME"
    else
        podman compose build --no-cache "$SERVICE_NAME"
    fi
else
    echo "正在强制重建所有服务镜像..."
    echo ""
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose build --no-cache
    else
        podman compose build --no-cache
    fi
fi

echo ""
echo "✅ 强制构建完成"

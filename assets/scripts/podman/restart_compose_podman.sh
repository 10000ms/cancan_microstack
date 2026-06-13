#!/bin/bash

# Podman Compose 重启脚本
# 用于重启整个 Podman Compose 集群或单个服务

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "重启 Podman Compose 集群"
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

# 检查是否指定了服务名称
SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "正在重启服务: $SERVICE_NAME"
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose restart "$SERVICE_NAME"
    else
        podman compose restart "$SERVICE_NAME"
    fi
else
    echo "正在重启所有服务..."
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose restart
    else
        podman compose restart
    fi
fi

echo ""
echo "等待服务重启..."
sleep 3

# 显示服务状态
echo ""
echo "========================================="
echo "服务状态"
echo "========================================="

if [ "$COMPOSE_CMD" = "podman-compose" ]; then
    podman-compose ps
else
    podman compose ps
fi

echo ""
echo "✅ Podman Compose 重启完成"

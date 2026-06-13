#!/bin/bash

# Docker Compose 重启脚本
# 用于重启整个 Docker Compose 集群

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "重启 Docker Compose 集群"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 先停止服务
echo "步骤 1: 停止 Docker Compose 集群..."
"$SCRIPT_DIR/stop_compose.sh"

# 等待 3 秒
echo ""
echo "等待 3 秒..."
sleep 3

# 再启动服务
echo ""
echo "步骤 2: 启动 Docker Compose 集群..."
"$SCRIPT_DIR/start_compose.sh"

echo ""
echo "========================================="
echo "✅ Docker Compose 集群重启完成"
echo "========================================="

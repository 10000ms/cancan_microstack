#!/bin/bash

# 一键停止所有服务脚本
# 包括 controllersrv 和 Docker Compose 集群

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "一键停止所有服务"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 步骤 1: 停止 Docker Compose 集群
echo "步骤 1: 停止 Docker Compose 集群..."
"$SCRIPT_DIR/stop_compose.sh" || true

echo ""
echo "等待 3 秒..."
sleep 3

# 步骤 2: 停止 controllersrv
echo ""
echo "步骤 2: 停止 controllersrv..."
"$SCRIPT_DIR/stop.sh" || true

echo ""
echo "========================================="
echo "✅ 所有服务已停止"
echo "========================================="
echo ""
echo "提示："
echo "  - 重新启动所有服务: ./cmd/controllersrv/start_all.sh"
echo ""

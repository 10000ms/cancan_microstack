#!/bin/bash

# 一键重建所有服务脚本（Podman 版本）
# 包括重启 controllersrv 和重建 Podman Compose 集群

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "一键重建所有服务（Podman 环境）"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 步骤 1: 重启 controllersrv
echo "步骤 1: 重启 controllersrv (宿主机)..."
# Podman 版本没有 restart_podman.sh，通常使用 start/stop
"$SCRIPT_DIR/stop_all_podman.sh" || true
sleep 2
"$SCRIPT_DIR/start_podman.sh"

echo ""
echo "等待 5 秒..."
sleep 5

# 步骤 2: 重建 Podman Compose 集群
echo ""
echo "步骤 2: 重建 Podman Compose 集群..."
"$SCRIPT_DIR/rebuild_compose_podman.sh"

echo ""
echo "========================================="
echo "✅ 所有服务重建完成"
echo "========================================="

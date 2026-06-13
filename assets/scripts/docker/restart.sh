#!/bin/bash

# controllersrv 重启脚本
# 用于重启宿主机上运行的 controllersrv 服务

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "重启 controllersrv"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 先停止服务
echo "步骤 1: 停止 controllersrv..."
"$SCRIPT_DIR/stop.sh" || true

# 等待 2 秒
echo ""
echo "等待 2 秒..."
sleep 2

# 再启动服务
echo ""
echo "步骤 2: 启动 controllersrv..."
"$SCRIPT_DIR/start.sh"

echo ""
echo "========================================="
echo "✅ controllersrv 重启完成"
echo "========================================="

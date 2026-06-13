#!/bin/bash

# 一键启动所有服务脚本
# 包括 controllersrv 和 Docker Compose 集群

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "一键启动所有服务"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 步骤 1: 启动 controllersrv
echo "步骤 1: 启动 controllersrv (宿主机)..."
"$SCRIPT_DIR/start.sh"

echo ""
echo "等待 5 秒，确保 controllersrv 完全启动..."
sleep 5

# 步骤 2: 启动 Docker Compose 集群
echo ""
echo "步骤 2: 启动 Docker Compose 集群..."
"$SCRIPT_DIR/start_compose.sh"

echo ""
echo "========================================="
echo "✅ 所有服务启动完成"
echo "========================================="
echo ""
echo "服务访问地址："
echo "  - controllersrv: http://localhost:22100"
echo "  - infrasrv:      http://localhost:8080"
echo "  - opsbffsrv:     http://localhost:8081"
echo "  - besrv:         http://localhost:8082"
echo ""
echo "快捷命令："
echo "  - 查看 controllersrv 日志: tail -f logs/controllersrv.log"
echo "  - 查看 Docker 服务日志:    docker-compose logs -f [服务名]"
echo "  - 停止所有服务:           ./cmd/controllersrv/stop_all.sh"
echo ""

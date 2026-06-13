#!/bin/bash

# Docker Compose 停止脚本
# 用于停止整个 Docker Compose 集群

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "停止 Docker Compose 集群"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "⚠️  Docker 未运行"
    exit 1
fi

# 停止所有服务
echo "正在停止所有 Docker Compose 服务..."
docker-compose down

echo ""
echo "✅ Docker Compose 集群已停止"
echo ""
echo "提示："
echo "  - 如需删除数据卷: docker-compose down -v"
echo "  - 如需重新启动: ./cmd/controllersrv/start_compose.sh"

#!/bin/bash

# Docker Compose 启动脚本
# 用于启动整个 Docker Compose 集群

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "启动 Docker Compose 集群"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

# 检查 docker-compose.yml 是否存在
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 未找到 docker-compose.yml 文件"
    exit 1
fi

# 启动 Docker Compose
echo "正在启动 Docker Compose 服务..."
echo "包括: postgres, redis, infrasrv, opsbffsrv, besrv"
echo ""

docker-compose up -d

# 等待服务启动
echo ""
echo "等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "========================================="
echo "服务状态检查"
echo "========================================="
docker-compose ps

echo ""
echo "✅ Docker Compose 集群启动完成"
echo ""
echo "服务访问地址："
echo "  - infrasrv:    http://localhost:8080"
echo "  - opsbffsrv:   http://localhost:8081"
echo "  - besrv:       http://localhost:8082"
echo "  - PostgreSQL:  localhost:5432 (如已暴露)"
echo "  - Redis:       localhost:6379 (如已暴露)"
echo ""
echo "查看日志: docker-compose logs -f [服务名]"
echo "停止服务: ./cmd/controllersrv/stop_compose.sh"
echo "重启服务: ./cmd/controllersrv/restart_compose.sh"

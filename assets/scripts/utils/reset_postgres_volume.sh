#!/bin/bash

# PostgreSQL 卷重置脚本
# 用于解决 PG 版本升级导致的数据目录结构不兼容问题

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "重置 PostgreSQL 数据卷"
echo "========================================="
echo "警告：这将删除现有的 PostgreSQL 数据卷！"
echo "仅在开发环境或数据已备份的情况下执行此操作。"
echo ""

read -p "确定要继续吗？(y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作已取消"
    exit 0
fi

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检测容器引擎
COMPOSE_CMD=""
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
    CONTAINER_CMD="podman"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    CONTAINER_CMD="docker"
else
    echo "❌ 未找到 docker-compose 或 podman-compose"
    exit 1
fi

echo "1. 停止所有相关服务（解决依赖问题）..."
# 先停止所有业务服务，因为它们依赖数据库
if [ -f "docker-compose.services.yml" ]; then
    $COMPOSE_CMD -f docker-compose.services.yml down 2>/dev/null || true
fi
# 停止基础设施服务
if [ -f "docker-compose.infra.yml" ]; then
    $COMPOSE_CMD -f docker-compose.infra.yml down 2>/dev/null || true
fi

echo "2. 强制删除 PostgreSQL 容器..."
$CONTAINER_CMD rm -f my_app_postgres 2>/dev/null || true

echo "3. 强制删除其他相关容器（确保没有残留依赖）..."
$CONTAINER_CMD rm -f my_app_redis my_app_infrasrv my_app_opsbffsrv my_app_besrv my_app_pgweb my_app_caddy 2>/dev/null || true

echo "4. 删除数据卷 my_app_postgres_data..."
# 使用 -f 强制删除
$CONTAINER_CMD volume rm -f my_app_postgres_data 2>/dev/null || echo "数据卷可能已被删除"

echo ""
echo "✅ 数据卷已清理"
echo "请重新运行启动脚本以初始化新的数据库："
echo "  ./scripts/docker/start_compose.sh"
echo "  或"
echo "  ./scripts/podman/start_compose_podman.sh"

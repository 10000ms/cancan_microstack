#!/bin/bash

# Podman Compose 启动脚本 (详细状态 + 优化版)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOG_PREFIX="[compose]"
STACK_PREFIX="${MY_APP_STACK_PREFIX:-my_app}"
CADDY_CONTAINER="${STACK_PREFIX}_caddy"

echo "$LOG_PREFIX 正在初始化 Podman Compose 集群..."
cd "$PROJECT_ROOT"

# 1. 确定命令
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
elif podman compose version > /dev/null 2>&1; then
    COMPOSE_CMD="podman compose"
else
    echo "❌ 未找到 Podman Compose"
    exit 1
fi
echo "$LOG_PREFIX 使用命令: $COMPOSE_CMD"

# 2. 启动服务 (Up -d)
# 策略：直接运行 up -d，让工具处理依赖和状态
echo "$LOG_PREFIX 正在启动容器 (up -d)..."
echo "$LOG_PREFIX 如有镜像拉取错误，请检查网络或配置"

# 捕获错误但让流程继续，以便后续检查状态
if [ "$COMPOSE_CMD" = "podman-compose" ]; then
    podman-compose up -d 2>&1 | sed "s/^/$LOG_PREFIX /" || echo "⚠️  $LOG_PREFIX 启动命令返回错误，继续检查状态..."
else
    podman compose up -d 2>&1 | sed "s/^/$LOG_PREFIX /" || echo "⚠️  $LOG_PREFIX 启动命令返回错误，继续检查状态..."
fi

check_caddy_health() {
    local status
    status=$(podman inspect -f '{{ .State.Healthcheck.Status }}' "$CADDY_CONTAINER" 2>/dev/null || echo "unknown")
    if [ "$status" = "healthy" ]; then
        return 0
    fi
    if [ "$status" = "unhealthy" ] || [ "$status" = "starting" ]; then
        return 1
    fi
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/health" || echo "000")
    [ "$http_code" = "200" ]
}

# 3. 详细健康检查 (快速反馈)
echo "$LOG_PREFIX 正在等待核心服务健康检查..."
MAX_RETRIES=60

printf "$LOG_PREFIX 等待就绪: "

for ((i=1; i<=MAX_RETRIES; i++)); do
    if check_caddy_health; then
        echo ""
        echo "✅ $LOG_PREFIX [SUCCESS] Caddy 健康检查通过"
        echo ""
        echo "📊 当前容器状态:"
        podman ps --filter "name=${STACK_PREFIX}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | sed "s/^/   /"
        exit 0
    fi
    printf "."
    sleep 2
done

echo ""
echo "❌ $LOG_PREFIX 启动超时！Caddy 健康检查未通过."
echo "🔎 正在检查容器日志 (最后 20 行):"
echo "--- $CADDY_CONTAINER ---"
podman logs --tail 20 "$CADDY_CONTAINER" 2>/dev/null || echo "(无日志)"
echo "--- ${STACK_PREFIX}_infrasrv ---"
podman logs --tail 20 "${STACK_PREFIX}_infrasrv" 2>/dev/null || echo "(无日志)"

exit 1

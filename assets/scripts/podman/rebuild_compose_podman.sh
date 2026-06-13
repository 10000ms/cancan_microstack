#!/bin/bash

# Podman Compose 重建脚本 (详细日志版)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOG_PREFIX="[rebuild]"

echo "$LOG_PREFIX 正在初始化..."
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

SERVICE_NAME="$1"

if [ -n "$SERVICE_NAME" ]; then
    echo "$LOG_PREFIX 正在重建服务: $SERVICE_NAME"
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose up -d --build "$SERVICE_NAME" 2>&1 | sed "s/^/$LOG_PREFIX /"
    else
        podman compose up -d --build "$SERVICE_NAME" 2>&1 | sed "s/^/$LOG_PREFIX /"
    fi
else
    echo "$LOG_PREFIX 正在重建所有服务 (这可能需要几分钟)..."
    if [ "$COMPOSE_CMD" = "podman-compose" ]; then
        podman-compose up -d --build 2>&1 | sed "s/^/$LOG_PREFIX /"
    else
        podman compose up -d --build 2>&1 | sed "s/^/$LOG_PREFIX /"
    fi
    
    # 健康检查
    echo "$LOG_PREFIX 正在等待服务就绪..."
    URL="http://localhost:8080/health"
    MAX_RETRIES=60
    
    for ((i=1; i<=MAX_RETRIES; i++)); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" || echo "Err")
        if [ "$HTTP_CODE" == "200" ]; then
            echo "✅ $LOG_PREFIX 重建并启动成功！"
            exit 0
        fi
        echo -n "."
        sleep 2
    done
    echo ""
    echo "⚠️  $LOG_PREFIX 启动超时"
fi

echo "✅ $LOG_PREFIX 重建指令完成"

#!/bin/bash

# Podman Compose 停止脚本 (强力版)
# 能够识别并停止所有相关容器，包括僵尸进程

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

LOG_PREFIX="[compose-stop]"

echo "$LOG_PREFIX 正在扫描运行中的服务..."
cd "$PROJECT_ROOT"

# 1. 发现容器
# 搜索逻辑：匹配 'my_app' (项目前缀) 或明确的服务名称
# 使用 --no-trunc 确保名字完整
TARGETS=$(podman ps --format "{{.Names}}" | grep -E "my_app|postgres.internal|redis.internal|rabbitmq.internal|infrasrv|opsbffsrv|besrv" || true)

if [ -z "$TARGETS" ]; then
    echo "✅ $LOG_PREFIX 没有发现运行中的相关容器"
    exit 0
fi

# 转换换行符为空格，形成列表
CONTAINER_LIST=$(echo "$TARGETS" | tr '\n' ' ')

echo "$LOG_PREFIX 发现以下容器正在运行:"
echo "$TARGETS" | sed "s/^/  - /"
echo ""

# 2. 停止容器 (并行发送 SIGTERM)
echo "$LOG_PREFIX 正在发送停止信号 (Timeout=10s)..."
# 忽略报错，确保脚本继续执行
podman stop -t 10 $CONTAINER_LIST 2>/dev/null || true

# 3. 检查残留并强制清理
echo "$LOG_PREFIX 检查残留..."
REMAINING=$(podman ps --format "{{.Names}}" | grep -E "my_app|postgres.internal|redis.internal|rabbitmq.internal|infrasrv|opsbffsrv|besrv" || true)

if [ -n "$REMAINING" ]; then
    echo "⚠️  $LOG_PREFIX 以下容器未响应停止信号，正在强制清除 (kill)..."
    echo "$REMAINING" | sed "s/^/  - /"
    
    REMAINING_LIST=$(echo "$REMAINING" | tr '\n' ' ')
    podman stop -t 0 $REMAINING_LIST 2>/dev/null || podman rm -f $REMAINING_LIST 2>/dev/null || true
    
    # 再次检查
    FINAL_CHECK=$(podman ps --format "{{.Names}}" | grep -E "my_app|postgres.internal|redis.internal|rabbitmq.internal" || true)
    if [ -n "$FINAL_CHECK" ]; then
        echo "❌ $LOG_PREFIX 无法停止以下容器 (可能需要手动处理):"
        echo "$FINAL_CHECK"
        exit 1
    fi
    echo "✅ $LOG_PREFIX 已强制停止所有残留容器"
else
    echo "✅ $LOG_PREFIX 所有容器已正常停止"
fi
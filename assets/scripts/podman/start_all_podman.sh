#!/bin/bash

# 一键启动脚本（并行加速版）

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/server_log_data"
CONTROLLER_LOG="$LOG_DIR/controllersrv-startup.log"

mkdir -p "$LOG_DIR"

echo "========================================="
echo "🚀 一键极速启动 (Podman Parallel)"
echo "========================================="
echo "时间: $(date '+%H:%M:%S')"
echo ""

# 使用后台进程并行启动
(
    echo "🔵 [Task A] 启动 controllersrv..."
    if bash "$SCRIPT_DIR/start_podman.sh"; then
        echo "✅ [Task A] controllersrv OK"
    else
        echo "❌ [Task A] controllersrv 启动失败"
        if [ -f "$CONTROLLER_LOG" ]; then
            echo "---- controllersrv 最近日志 ----"
            tail -n 20 "$CONTROLLER_LOG"
            echo "--------------------------------"
        else
            echo "未找到 $CONTROLLER_LOG，可能脚本在初始化前终止"
        fi
        exit 1
    fi
) &
PID_A=$!

(
    echo "🟣 [Task B] 启动 Compose 集群..."
    # 调用我们优化过的 compose 启动脚本
    bash "$SCRIPT_DIR/start_compose_podman.sh"
) &
PID_B=$!

# 等待 Compose 任务 (它有详细输出)
wait $PID_B
STATUS_B=$?

# 等待 Controller 任务
wait $PID_A
STATUS_A=$?

echo ""
echo "========================================="
if [ $STATUS_A -eq 0 ] && [ $STATUS_B -eq 0 ]; then
    echo "✅ 所有服务启动成功！"
    echo "========================================="
    echo "访问地址:"
    echo "  - Caddy:       http://localhost:8080"
    echo "  - Controllers: http://localhost:22100"
    echo "  - PgWeb:       http://localhost:8080/v1/opsbffsrv/pgweb/"
    echo ""
else
    echo "❌ 启动包含错误"
    exit 1
fi

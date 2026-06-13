#!/bin/bash

# 一键停止脚本（Podman 并行版）

# 设置脚本错误时退出
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "🛑 一键停止所有服务"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 并行执行停止
(
    echo "🔵 [任务 1] 停止 controllersrv..."
    bash "$SCRIPT_DIR/stop.sh" && echo "✅ [任务 1] controllersrv 已停止"
) &
PID_1=$!

(
    echo "🟣 [任务 2] 停止 Podman Compose 集群..."
    bash "$SCRIPT_DIR/stop_compose_podman.sh" && echo "✅ [任务 2] Compose 集群已停止"
) &
PID_2=$!

wait $PID_1
wait $PID_2

echo ""
echo "========================================="
echo "✅ 所有服务已停止"
echo "========================================="
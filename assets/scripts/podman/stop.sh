#!/bin/bash

# controllersrv 停止脚本（详细版）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PID_FILE="$PROJECT_ROOT/server_log_data/controllersrv.pid"
LOG_PREFIX="[controllersrv-stop]"
CONTROLLER_PORT=22100

stop_by_pid() {
    local target_pid=$1
    echo "$LOG_PREFIX 正在发送 SIGTERM 信号给 PID: $target_pid ..."
    if ! kill "$target_pid" 2>/dev/null; then
        echo "ℹ️  $LOG_PREFIX PID $target_pid 已不存在 / already gone"
        return 0
    fi

    echo -n "$LOG_PREFIX 等待进程退出 / waiting for exit"
    for i in {1..10}; do
        if ! ps -p "$target_pid" > /dev/null 2>&1; then
            echo ""
            echo "✅ $LOG_PREFIX PID $target_pid 已正常停止"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo ""
    echo "⚠️  $LOG_PREFIX PID $target_pid 响应超时，正在强制 kill -9 ..."
    kill -9 "$target_pid" 2>/dev/null || true
    echo "✅ $LOG_PREFIX PID $target_pid 已强制停止"
}

stop_by_port() {
    # 兜底逻辑：当 PID 文件缺失时，通过端口检测正在运行的 controllersrv 实例
    # Fallback: kill processes listening on controllersrv port when the PID file is missing
    if ! command -v lsof >/dev/null 2>&1; then
        echo "ℹ️  $LOG_PREFIX 未运行 (缺少 lsof，无法检测端口)"
        exit 0
    fi

    local port_pids
    port_pids=$(lsof -i :$CONTROLLER_PORT -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -z "$port_pids" ]; then
        echo "ℹ️  $LOG_PREFIX 未运行 (未检测到监听 $CONTROLLER_PORT 的进程)"
        exit 0
    fi

    echo "⚠️  $LOG_PREFIX 未找到 PID 文件，但检测到监听 $CONTROLLER_PORT 的进程: $port_pids"
    for pid in $port_pids; do
        stop_by_pid "$pid"
    done
    echo "✅ $LOG_PREFIX 已通过端口兜底逻辑停止 controllersrv"
}

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ! ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "ℹ️  $LOG_PREFIX 进程 $OLD_PID 不存在，清理残留文件"
        rm -f "$PID_FILE"
        stop_by_port
        exit 0
    fi

    stop_by_pid "$OLD_PID"
    rm -f "$PID_FILE"
    exit 0
fi

stop_by_port

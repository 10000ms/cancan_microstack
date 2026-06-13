#!/bin/bash

# controllersrv 启动脚本（Podman 详细日志版）

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 日志前缀
LOG_PREFIX="[controllersrv]"

echo "$LOG_PREFIX 正在初始化..."
echo "$LOG_PREFIX 项目根目录: $PROJECT_ROOT"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查环境
if [ -d "venv" ]; then
    source venv/bin/activate
    PYTHON_CMD="python"
    echo "$LOG_PREFIX 激活虚拟环境: $(which python)"
else
    PYTHON_CMD="python3"
    echo "$LOG_PREFIX 使用系统 Python: $(which python3)"
fi

# 检查 Python 版本
PY_VERSION=$($PYTHON_CMD --version 2>&1)
echo "$LOG_PREFIX Python 版本: $PY_VERSION"

# 设置环境变量
export NE_CONFIG=prod
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/src/libs:$PROJECT_ROOT/cmd:$PYTHONPATH"
echo "$LOG_PREFIX 环境变量 PYTHONPATH 设置完成"

# 创建日志目录
mkdir -p "$PROJECT_ROOT/server_log_data"
LOG_FILE="$PROJECT_ROOT/server_log_data/controllersrv-startup.log"
PID_FILE="$PROJECT_ROOT/server_log_data/controllersrv.pid"

# 清理旧 PID
if [ -f "$PID_FILE" ]; then
    rm -f "$PID_FILE"
fi

# 检查端口
if lsof -i :22100 -sTCP:LISTEN -t >/dev/null ; then
    echo "❌ $LOG_PREFIX 端口 22100 被占用，无法启动"
    exit 1
fi

# 启动服务
echo "$LOG_PREFIX 正在启动后台进程..."
echo "$LOG_PREFIX 日志输出至: $LOG_FILE"

nohup $PYTHON_CMD cmd/controllersrv/run.py > "$LOG_FILE" 2>&1 &
SERVICE_PID=$!
echo $SERVICE_PID > "$PID_FILE"
echo "$LOG_PREFIX 进程已启动，PID: $SERVICE_PID"

# 健康检查
echo "$LOG_PREFIX 等待健康检查 (http://localhost:22100/internal/health)..."
MAX_RETRIES=30
for ((i=1; i<=MAX_RETRIES; i++)); do
    # 检查进程是否存在
    if ! ps -p $SERVICE_PID > /dev/null 2>&1; then
        echo ""
        echo "❌ $LOG_PREFIX 进程意外退出！"
        echo "---------------------------------------------------"
        tail -n 10 "$LOG_FILE"
        echo "---------------------------------------------------"
        rm -f "$PID_FILE"
        exit 1
    fi

    if curl -s http://localhost:22100/internal/health >/dev/null; then
        echo "✅ $LOG_PREFIX 健康检查通过！服务已就绪。"
        exit 0
    fi
    
    sleep 1
done

echo "❌ $LOG_PREFIX 启动超时，强制停止..."
kill $SERVICE_PID 2>/dev/null || true
rm -f "$PID_FILE"
exit 1

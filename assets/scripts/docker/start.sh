#!/bin/bash

# controllersrv 启动脚本
# 用于在宿主机上启动 controllersrv 服务

# 设置脚本错误时退出
set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "启动 controllersrv"
echo "========================================="
echo "项目目录: $PROJECT_ROOT"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.11+"
    exit 1
fi

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查并激活虚拟环境
if [ -d "venv" ]; then
    echo "使用虚拟环境: $PROJECT_ROOT/venv"
    source venv/bin/activate
    PYTHON_CMD="python"
else
    echo "警告: 未找到虚拟环境，使用系统 Python"
    PYTHON_CMD="python3"
fi

# 设置环境变量（统一 PYTHONPATH 配置：src 和 cmd）
export NE_CONFIG=prod
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/src/libs:$PROJECT_ROOT/cmd:$PYTHONPATH"

# 检查依赖是否安装
if [ ! -d "venv" ]; then
    echo "提示: 未找到虚拟环境，建议先运行 'python3 -m venv venv' 创建虚拟环境"
    echo "然后运行 'source venv/bin/activate && pip install -r requirements.txt' 安装依赖"
fi

# 启动 controllersrv
echo "正在启动 controllersrv (端口: 22100)..."
echo ""

mkdir -p logs/

# 后台启动服务（日志由应用本身的 logging 模块处理）
$PYTHON_CMD cmd/controllersrv/run.py &

# 保存 PID
CONTROLLER_PID=$!
echo $CONTROLLER_PID > /tmp/controllersrv.pid

echo "✅ controllersrv 已启动"
echo "   PID: $CONTROLLER_PID"
echo "   日志目录: server_log_data/"
echo "   访问地址: http://localhost:22100"
echo ""
echo "查看日志: tail -f server_log_data/controllersrv-*.log"
echo "停止服务: ./cmd/controllersrv/stop.sh"
echo ""

# 等待 2 秒检查进程是否还在运行
sleep 2
if ps -p $CONTROLLER_PID > /dev/null; then
    echo "✅ controllersrv 运行正常"
else
    echo "❌ controllersrv 启动失败，请检查日志"
    exit 1
fi

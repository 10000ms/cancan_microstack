#!/bin/bash

# controllersrv 停止脚本
# 用于停止宿主机上运行的 controllersrv 服务

# 设置脚本错误时退出
set -e

echo "========================================="
echo "停止 controllersrv"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 检查 PID 文件是否存在
if [ ! -f "/tmp/controllersrv.pid" ]; then
    echo "⚠️  未找到 PID 文件，controllersrv 可能未运行"
    echo "   尝试查找进程..."
    
    # 尝试通过进程名查找
    CONTROLLER_PID=$(ps aux | grep "cmd/controllersrv/run.py" | grep -v grep | awk '{print $2}')
    
    if [ -z "$CONTROLLER_PID" ]; then
        echo "❌ 未找到 controllersrv 进程"
        exit 1
    fi
else
    # 从文件读取 PID
    CONTROLLER_PID=$(cat /tmp/controllersrv.pid)
fi

echo "找到 controllersrv 进程: PID=$CONTROLLER_PID"

# 检查进程是否存在
if ! ps -p $CONTROLLER_PID > /dev/null; then
    echo "⚠️  进程 $CONTROLLER_PID 不存在，可能已经停止"
    rm -f /tmp/controllersrv.pid
    exit 0
fi

# 发送 SIGTERM 信号（优雅关闭）
echo "正在发送 SIGTERM 信号..."
kill -TERM $CONTROLLER_PID

# 等待进程结束（最多等待 10 秒）
echo "等待进程结束..."
for i in {1..10}; do
    if ! ps -p $CONTROLLER_PID > /dev/null; then
        echo "✅ controllersrv 已优雅停止"
        rm -f /tmp/controllersrv.pid
        exit 0
    fi
    sleep 1
done

# 如果还没结束，强制杀死
echo "⚠️  进程未响应 SIGTERM，发送 SIGKILL 强制停止..."
kill -KILL $CONTROLLER_PID
sleep 1

if ! ps -p $CONTROLLER_PID > /dev/null; then
    echo "✅ controllersrv 已强制停止"
    rm -f /tmp/controllersrv.pid
else
    echo "❌ 无法停止 controllersrv 进程"
    exit 1
fi

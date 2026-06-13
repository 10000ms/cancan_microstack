#!/bin/bash

# 验证异步操作是否真的影响了容器

echo "========================================="
echo "验证异步操作对容器的实际影响"
echo "========================================="
echo ""

# 记录当前容器启动时间
BEFORE=$(podman inspect my_app_besrv --format '{{.State.StartedAt}}')
echo "容器当前启动时间: $BEFORE"
echo ""

# 执行重启操作
echo "========================================="
echo "执行重启操作..."
echo "========================================="
OPERATION_ID=$(curl -s -X POST 'http://127.0.0.1:8080/v1/opsbffsrv/async/service/restart' \
  -H 'Content-Type: application/json' \
  -d '{"service_name": "besrv"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['data']['operation_id'])")

echo "Operation ID: $OPERATION_ID"
echo ""

# 等待操作完成
echo "等待操作完成（10秒）..."
sleep 10
echo ""

# 检查新的启动时间
AFTER=$(podman inspect my_app_besrv --format '{{.State.StartedAt}}')
echo "容器新的启动时间: $AFTER"
echo ""

# 比较
if [ "$BEFORE" != "$AFTER" ]; then
    echo "✅ 验证成功：容器确实被重启了！"
    echo "   启动时间已改变"
else
    echo "❌ 验证失败：容器未被重启"
    echo "   启动时间未改变"
fi
echo ""

# 检查 controllersrv 任务状态
echo "========================================="
echo "controllersrv 任务执行状态:"
echo "========================================="
curl -s "http://localhost:22100/v1/controllersrv/task/status?serial_number=$OPERATION_ID" | \
  python3 -c "import sys, json; t=json.load(sys.stdin)['data']['task']; \
    print(f\"任务状态: {t['status']}\"); \
    print(f\"开始时间: {t.get('started_at', 'N/A')}\"); \
    print(f\"完成时间: {t.get('finished_at', 'N/A')}\"); \
    print(f\"执行结果: {t.get('result', {})}\"); \
    print(f\"错误信息: {t.get('error', 'None')}\")"
echo ""

# 检查 infrasrv 操作记录
echo "========================================="
echo "infrasrv 操作记录状态:"
echo "========================================="
curl -s "http://127.0.0.1:8080/v1/opsbffsrv/operation/status?operation_id=$OPERATION_ID" | \
  python3 -c "import sys, json; op=json.load(sys.stdin)['data']['operation']; \
    print(f\"操作ID: {op['operation_id']}\"); \
    print(f\"操作类型: {op['operation_type']}\"); \
    print(f\"服务名称: {op['service_name']}\"); \
    print(f\"操作状态: {op['status']}\"); \
    print(f\"开始时间: {op.get('started_at', 'N/A')}\"); \
    print(f\"完成时间: {op.get('completed_at', 'N/A')}\")"
echo ""

echo "========================================="
echo "验证完成"
echo "========================================="

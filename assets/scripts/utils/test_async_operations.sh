#!/bin/bash

# 异步操作接口完整测试脚本
# 测试 opsbffsrv 的所有异步操作接口

set -e

BASE_URL="http://127.0.0.1:8080/v1/opsbffsrv"
SERVICE_NAME="besrv"

echo "========================================="
echo "异步操作接口测试"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试结果统计
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 测试函数
test_api() {
    local test_name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${YELLOW}测试 ${TOTAL_TESTS}: ${test_name}${NC}"
    
    if [ "$method" == "GET" ]; then
        response=$(curl -s "${BASE_URL}${endpoint}")
    else
        response=$(curl -s -X POST "${BASE_URL}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    # 检查是否成功
    success=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))")
    
    if [ "$success" == "True" ]; then
        echo -e "${GREEN}✓ 通过${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        
        # 提取 operation_id (如果有)
        operation_id=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin).get('data', {}); print(data.get('operation_id', ''))" 2>/dev/null || echo "")
        if [ -n "$operation_id" ]; then
            echo "  Operation ID: $operation_id"
            echo "$operation_id" >> /tmp/test_operation_ids.txt
        fi
    else
        echo -e "${RED}✗ 失败${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo "  响应: $response"
    fi
    echo ""
}

# 清理临时文件
rm -f /tmp/test_operation_ids.txt

echo "========================================="
echo "1. 测试异步服务操作接口"
echo "========================================="
echo ""

# 1. 测试重启服务
test_api "重启服务" "POST" "/async/service/restart" "{\"service_name\": \"${SERVICE_NAME}\"}"

# 等待一下
sleep 1

# 2. 测试启动服务
test_api "启动服务" "POST" "/async/service/start" "{\"service_name\": \"${SERVICE_NAME}\"}"

sleep 1

# 3. 测试停止服务
test_api "停止服务" "POST" "/async/service/stop" "{\"service_name\": \"${SERVICE_NAME}\"}"

sleep 1

# 4. 测试扩缩容服务
test_api "扩缩容服务" "POST" "/async/service/scale" "{\"service_name\": \"${SERVICE_NAME}\", \"replicas\": 2}"

sleep 1

echo "========================================="
echo "2. 测试操作状态查询接口"
echo "========================================="
echo ""

# 等待操作执行
sleep 3

# 6. 查询最后一个操作的状态
if [ -f /tmp/test_operation_ids.txt ]; then
    last_operation_id=$(tail -1 /tmp/test_operation_ids.txt)
    test_api "查询操作状态" "GET" "/operation/status?operation_id=${last_operation_id}" ""
fi

# 7. 列出所有操作
test_api "列出所有操作 (限制5条)" "GET" "/operation/list?limit=5" ""

# 8. 按服务名筛选
test_api "按服务名筛选" "GET" "/operation/list?service_name=${SERVICE_NAME}.service&limit=3" ""

# 9. 按状态筛选
test_api "按状态筛选" "GET" "/operation/list?status=success&limit=3" ""

# 10. 组合筛选
test_api "组合筛选" "GET" "/operation/list?service_name=${SERVICE_NAME}.service&status=success&limit=3" ""

echo "========================================="
echo "测试结果汇总"
echo "========================================="
echo ""
echo "总测试数: ${TOTAL_TESTS}"
echo -e "${GREEN}通过: ${PASSED_TESTS}${NC}"
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}失败: ${FAILED_TESTS}${NC}"
else
    echo "失败: ${FAILED_TESTS}"
fi
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 部分测试失败${NC}"
    exit 1
fi

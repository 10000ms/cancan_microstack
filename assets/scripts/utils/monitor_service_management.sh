#!/bin/bash
# 服务管理监控脚本 / Service Management Monitoring Script

set -e

# 颜色定义 / Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_data() {
    echo -e "${CYAN}$1${NC}"
}

print_header "服务管理监控 / Service Management Monitoring"

# 1. 检查 controllersrv
print_info "检查 controllersrv / Checking controllersrv..."

CONTROLLERSRV_HEALTH=$(curl -s http://localhost:22100/internal/health 2>/dev/null || echo "failed")

if echo "$CONTROLLERSRV_HEALTH" | grep -q "success"; then
    print_success "controllersrv 正常 / controllersrv is healthy"
else
    print_error "controllersrv 异常 / controllersrv is unhealthy"
fi

# 2. 检查 infrasrv
print_info "检查 infrasrv / Checking infrasrv..."

INFRASRV_HEALTH=$(curl -s http://localhost:8080/internal/health 2>/dev/null || echo "failed")

if echo "$INFRASRV_HEALTH" | grep -q "success"; then
    print_success "infrasrv 正常 / infrasrv is healthy"
else
    print_error "infrasrv 异常 / infrasrv is unhealthy"
fi

# 3. 检查 opsbffsrv
print_info "检查 opsbffsrv / Checking opsbffsrv..."

OPSBFFSRV_HEALTH=$(curl -s http://localhost:8081/internal/health 2>/dev/null || echo "failed")

if echo "$OPSBFFSRV_HEALTH" | grep -q "success"; then
    print_success "opsbffsrv 正常 / opsbffsrv is healthy"
else
    print_error "opsbffsrv 异常 / opsbffsrv is unhealthy"
fi

# 4. 查询最近的操作记录
print_header "最近的服务操作记录 / Recent Service Operations"

print_info "查询最近 10 条操作 / Querying last 10 operations..."

OPERATIONS=$(curl -s "http://localhost:8081/v1/opsbffsrv/operation/list?page=1&page_size=10" 2>/dev/null || echo '{"success":false}')

if echo "$OPERATIONS" | grep -q '"success":true'; then
    print_success "操作记录查询成功 / Operations query successful"
    
    # 使用 jq 格式化输出（如果已安装）
    if command -v jq &> /dev/null; then
        echo "$OPERATIONS" | jq -r '.data.records[] | "\(.operation_id) | \(.operation_type) | \(.service_name) | \(.status) | \(.created_time)"' | while read line; do
            print_data "  $line"
        done
    else
        print_data "$OPERATIONS"
        print_info "安装 jq 以获得更好的输出格式: brew install jq"
    fi
else
    print_warning "操作记录查询失败 / Operations query failed"
    echo "$OPERATIONS"
fi

# 5. 检查服务容器状态
print_header "Docker Compose 容器状态 / Docker Compose Container Status"

print_info "查询容器状态 / Querying container status..."

CONTAINER_STATUS=$(curl -s "http://localhost:22100/v1/controllersrv/compose/status" 2>/dev/null || echo '{"success":false}')

if echo "$CONTAINER_STATUS" | grep -q '"success":true'; then
    print_success "容器状态查询成功 / Container status query successful"
    
    if command -v jq &> /dev/null; then
        echo "$CONTAINER_STATUS" | jq -r '.data.services[] | "\(.name) | \(.state) | \(.status)"' | while read line; do
            # 根据状态着色
            if echo "$line" | grep -q "running"; then
                echo -e "${GREEN}  $line${NC}"
            elif echo "$line" | grep -q "exited"; then
                echo -e "${RED}  $line${NC}"
            else
                echo -e "${YELLOW}  $line${NC}"
            fi
        done
    else
        print_data "$CONTAINER_STATUS"
    fi
else
    print_warning "容器状态查询失败 / Container status query failed"
    echo "$CONTAINER_STATUS"
fi

# 6. 实时日志监控（可选）
print_header "实时日志监控 / Real-time Log Monitoring"

echo ""
print_info "选择要监控的服务日志 / Select service logs to monitor:"
echo "  1) controllersrv (宿主机日志 / Host logs)"
echo "  2) infrasrv (Docker Compose 日志 / Docker Compose logs)"
echo "  3) opsbffsrv (Docker Compose 日志 / Docker Compose logs)"
echo "  4) 跳过 / Skip"
echo ""

read -p "请输入选项 / Enter option (1-4): " LOG_CHOICE

case $LOG_CHOICE in
    1)
        print_info "监控 controllersrv 日志 / Monitoring controllersrv logs..."
        print_info "按 Ctrl+C 退出 / Press Ctrl+C to exit"
        sleep 2
        tail -f server_log_data/controllersrv.log 2>/dev/null || print_error "日志文件不存在 / Log file not found"
        ;;
    2)
        print_info "监控 infrasrv 日志 / Monitoring infrasrv logs..."
        print_info "按 Ctrl+C 退出 / Press Ctrl+C to exit"
        sleep 2
        docker-compose logs -f infrasrv.service 2>/dev/null || print_error "无法获取日志 / Cannot get logs"
        ;;
    3)
        print_info "监控 opsbffsrv 日志 / Monitoring opsbffsrv logs..."
        print_info "按 Ctrl+C 退出 / Press Ctrl+C to exit"
        sleep 2
        docker-compose logs -f opsbffsrv.service 2>/dev/null || print_error "无法获取日志 / Cannot get logs"
        ;;
    4)
        print_info "跳过日志监控 / Skipping log monitoring"
        ;;
    *)
        print_warning "无效选项 / Invalid option"
        ;;
esac

print_header "监控完成 / Monitoring Complete"

echo ""
print_info "其他有用的命令 / Other Useful Commands:"
echo ""
echo "  查看所有服务日志 / View all service logs:"
echo "    docker-compose logs -f"
echo ""
echo "  查看特定服务日志 / View specific service logs:"
echo "    docker-compose logs -f infrasrv.service"
echo "    docker-compose logs -f opsbffsrv.service"
echo ""
echo "  查看最近的错误 / View recent errors:"
echo "    docker-compose logs --tail=50 infrasrv.service | grep -i error"
echo ""
echo "  重启服务 / Restart services:"
echo "    curl -X POST http://localhost:22100/v1/controllersrv/service/restart \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"service_names\":[\"infrasrv.service\"]}'"
echo ""

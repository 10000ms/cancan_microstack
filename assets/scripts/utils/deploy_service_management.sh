#!/bin/bash
# 一键部署服务管理重构 / One-Click Deployment for Service Management Refactoring

set -e

# 颜色定义 / Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 检查项目根目录 / Check project root directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "请在项目根目录运行此脚本 / Please run this script from project root"
    exit 1
fi

PROJECT_ROOT=$(pwd)

print_header "一键部署服务管理重构 / One-Click Deployment"

# 步骤 1: 启动 controllersrv（宿主机运行）
print_header "步骤 1: 启动 controllersrv / Step 1: Start controllersrv"

print_info "检查 controllersrv 是否已运行 / Checking if controllersrv is running..."

if ps aux | grep -v grep | grep "cmd/controllersrv/run.py" > /dev/null; then
    print_warning "controllersrv 已经在运行 / controllersrv is already running"
    CONTROLLERSRV_PID=$(ps aux | grep -v grep | grep "cmd/controllersrv/run.py" | awk '{print $2}' | head -n1)
    print_info "PID: $CONTROLLERSRV_PID"
else
    print_info "启动 controllersrv / Starting controllersrv..."
    
    # 使用 nohup 在后台启动
    cd "$PROJECT_ROOT"
    export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/src/libs:$PROJECT_ROOT/cmd"
    
    nohup python3 cmd/controllersrv/run.py > server_log_data/controllersrv.log 2>&1 &
    CONTROLLERSRV_PID=$!
    
    echo $CONTROLLERSRV_PID > server_log_data/controllersrv.pid
    
    print_success "controllersrv 已启动 / controllersrv started (PID: $CONTROLLERSRV_PID)"
    
    # 等待 controllersrv 启动
    print_info "等待 controllersrv 启动（5秒）/ Waiting for controllersrv to start (5 seconds)..."
    sleep 5
    
    # 验证 controllersrv
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:22100/internal/health | grep -q "200"; then
        print_success "controllersrv 健康检查通过 / controllersrv health check passed"
    else
        print_error "controllersrv 健康检查失败 / controllersrv health check failed"
        print_info "查看日志: tail -f server_log_data/controllersrv.log"
        exit 1
    fi
fi

# 步骤 2: 使用 controllersrv 启动 Docker Compose 服务
print_header "步骤 2: 启动 Docker Compose 服务 / Step 2: Start Docker Compose Services"

print_info "通过 controllersrv API 启动 infrasrv 和 opsbffsrv / Starting infrasrv and opsbffsrv via controllersrv API..."

# 启动 infrasrv
START_RESPONSE=$(curl -s -X POST http://localhost:22100/v1/controllersrv/service/start \
    -H "Content-Type: application/json" \
    -d '{"service_names": ["infrasrv.service"]}')

if echo "$START_RESPONSE" | grep -q '"success":true'; then
    print_success "infrasrv 启动命令已发送 / infrasrv start command sent"
else
    print_error "infrasrv 启动失败 / infrasrv start failed"
    echo "$START_RESPONSE"
    exit 1
fi

# 等待 infrasrv 启动
print_info "等待 infrasrv 启动（10秒）/ Waiting for infrasrv to start (10 seconds)..."
sleep 10

# 验证 infrasrv
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/internal/health | grep -q "200"; then
    print_success "infrasrv 健康检查通过 / infrasrv health check passed"
else
    print_warning "infrasrv 健康检查失败，可能仍在启动中 / infrasrv health check failed, may still be starting"
fi

# 启动 opsbffsrv
START_RESPONSE=$(curl -s -X POST http://localhost:22100/v1/controllersrv/service/start \
    -H "Content-Type: application/json" \
    -d '{"service_names": ["opsbffsrv.service"]}')

if echo "$START_RESPONSE" | grep -q '"success":true'; then
    print_success "opsbffsrv 启动命令已发送 / opsbffsrv start command sent"
else
    print_error "opsbffsrv 启动失败 / opsbffsrv start failed"
    echo "$START_RESPONSE"
    exit 1
fi

# 等待 opsbffsrv 启动
print_info "等待 opsbffsrv 启动（10秒）/ Waiting for opsbffsrv to start (10 seconds)..."
sleep 10

# 验证 opsbffsrv
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/internal/health | grep -q "200"; then
    print_success "opsbffsrv 健康检查通过 / opsbffsrv health check passed"
else
    print_warning "opsbffsrv 健康检查失败，可能仍在启动中 / opsbffsrv health check failed, may still be starting"
fi

# 步骤 3: 运行集成测试
print_header "步骤 3: 运行集成测试 / Step 3: Run Integration Tests"

print_info "运行集成测试 / Running integration tests..."

if [ -f "$PROJECT_ROOT/test_service_management_refactoring.py" ]; then
    python3 "$PROJECT_ROOT/test_service_management_refactoring.py"
else
    print_warning "集成测试文件不存在 / Integration test file not found"
    print_info "手动运行: python test_service_management_refactoring.py"
fi

# 步骤 4: 部署完成总结
print_header "部署完成 / Deployment Complete"

print_success "所有服务已启动 / All services started"

echo ""
print_info "服务状态 / Service Status:"
echo "  - controllersrv: http://localhost:22100 (PID: $CONTROLLERSRV_PID)"
echo "  - infrasrv:      http://localhost:8080"
echo "  - opsbffsrv:     http://localhost:8081"
echo ""

print_info "监控命令 / Monitoring Commands:"
echo "  - controllersrv 日志 / controllersrv logs:"
echo "    tail -f server_log_data/controllersrv.log"
echo ""
echo "  - infrasrv 日志 / infrasrv logs:"
echo "    docker-compose logs -f infrasrv.service | grep ServiceManagementApp"
echo ""
echo "  - opsbffsrv 日志 / opsbffsrv logs:"
echo "    docker-compose logs -f opsbffsrv.service | grep AsyncOperationApp"
echo ""

print_info "停止服务 / Stop Services:"
echo "  - 停止 Docker Compose 服务 / Stop Docker Compose services:"
echo "    curl -X POST http://localhost:22100/v1/controllersrv/service/stop -H 'Content-Type: application/json' -d '{\"service_names\":[\"infrasrv.service\",\"opsbffsrv.service\"]}'"
echo ""
echo "  - 停止 controllersrv / Stop controllersrv:"
echo "    kill \$(cat server_log_data/controllersrv.pid)"
echo ""

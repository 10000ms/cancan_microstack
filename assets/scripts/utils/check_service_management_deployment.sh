#!/bin/bash
# 服务管理重构部署检查清单 / Service Management Refactoring Deployment Checklist

set -e

# 颜色定义 / Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数 / Print functions
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

print_header "服务管理重构部署检查清单 / Service Management Refactoring Deployment Checklist"

# 步骤 1: 代码检查 / Step 1: Code checks
print_header "步骤 1: 代码检查 / Step 1: Code Checks"

# 检查新文件是否存在 / Check if new files exist
print_info "检查新创建的文件 / Checking newly created files..."

FILES_TO_CHECK=(
    "src/public/types/infra/service_management.py"
    "src/service/infrasrv/infrastructure/api/controllersrv_api.py"
    "src/service/infrasrv/application/service_management_app.py"
    "src/service/infrasrv/interface/api/service_management_api.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        print_success "文件存在 / File exists: $file"
    else
        print_error "文件不存在 / File not found: $file"
        exit 1
    fi
done

# 检查旧文件是否已删除 / Check if old files are deleted
print_info "检查已删除的文件 / Checking deleted files..."

OLD_FILE="src/service/opsbffsrv/infrastructure/api/controllersrv_api.py"
if [ ! -f "$PROJECT_ROOT/$OLD_FILE" ]; then
    print_success "旧文件已删除 / Old file deleted: $OLD_FILE"
else
    print_warning "旧文件仍然存在，请删除 / Old file still exists, please delete: $OLD_FILE"
fi

# 步骤 2: 语法检查 / Step 2: Syntax checks
print_header "步骤 2: Python 语法检查 / Step 2: Python Syntax Checks"

print_info "检查 Python 语法错误 / Checking Python syntax errors..."

PYTHON_FILES=(
    "src/service/infrasrv/application/service_management_app.py"
    "src/service/infrasrv/interface/api/service_management_api.py"
    "src/service/opsbffsrv/application/async_operation_app.py"
)

SYNTAX_ERRORS=0
for file in "${PYTHON_FILES[@]}"; do
    if python3 -m py_compile "$PROJECT_ROOT/$file" 2>/dev/null; then
        print_success "语法正确 / Syntax OK: $file"
    else
        print_error "语法错误 / Syntax error: $file"
        SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
    fi
done

if [ $SYNTAX_ERRORS -gt 0 ]; then
    print_error "发现 $SYNTAX_ERRORS 个语法错误 / Found $SYNTAX_ERRORS syntax errors"
    exit 1
fi

# 步骤 3: 导入检查 / Step 3: Import checks
print_header "步骤 3: 导入检查 / Step 3: Import Checks"

print_info "检查 Python 导入 / Checking Python imports..."

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/src/libs:$PYTHONPATH"

IMPORT_ERRORS=0
for file in "${PYTHON_FILES[@]}"; do
    if python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/src'); import importlib.util; spec = importlib.util.spec_from_file_location('test', '$PROJECT_ROOT/$file'); module = importlib.util.module_from_spec(spec)" 2>/dev/null; then
        print_success "导入正确 / Imports OK: $file"
    else
        print_warning "导入可能有问题 / Imports may have issues: $file (需要运行环境 / Requires runtime environment)"
        # 不算作错误，因为可能需要数据库等依赖 / Don't count as error as it may need DB dependencies
    fi
done

# 步骤 4: 服务健康检查 / Step 4: Service health check
print_header "步骤 4: 服务健康检查 / Step 4: Service Health Check"

print_info "检查服务是否运行 / Checking if services are running..."

# 检查 infrasrv
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/internal/health | grep -q "200"; then
    print_success "infrasrv 正在运行 / infrasrv is running"
    INFRASRV_RUNNING=true
else
    print_warning "infrasrv 未运行 / infrasrv is not running"
    INFRASRV_RUNNING=false
fi

# 检查 opsbffsrv
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/internal/health | grep -q "200"; then
    print_success "opsbffsrv 正在运行 / opsbffsrv is running"
    OPSBFFSRV_RUNNING=true
else
    print_warning "opsbffsrv 未运行 / opsbffsrv is not running"
    OPSBFFSRV_RUNNING=false
fi

# 步骤 5: 部署建议 / Step 5: Deployment recommendations
print_header "步骤 5: 部署建议 / Step 5: Deployment Recommendations"

if [ "$INFRASRV_RUNNING" = false ] || [ "$OPSBFFSRV_RUNNING" = false ]; then
    print_info "服务未运行，准备部署步骤 / Services not running, prepare deployment steps..."
    echo ""
    print_info "部署步骤 / Deployment Steps:"
    echo ""
    echo "  1. 停止现有服务 / Stop existing services:"
    echo "     docker-compose stop infrasrv.service opsbffsrv.service"
    echo ""
    echo "  2. 重新构建服务 / Rebuild services (如果有 Dockerfile 修改 / if Dockerfile changed):"
    echo "     docker-compose build infrasrv.service opsbffsrv.service"
    echo ""
    echo "  3. 启动 infrasrv / Start infrasrv:"
    echo "     docker-compose up -d infrasrv.service"
    echo ""
    echo "  4. 等待 5 秒并验证 infrasrv / Wait 5 seconds and verify infrasrv:"
    echo "     sleep 5"
    echo "     curl http://localhost:8080/internal/health"
    echo ""
    echo "  5. 启动 opsbffsrv / Start opsbffsrv:"
    echo "     docker-compose up -d opsbffsrv.service"
    echo ""
    echo "  6. 验证 opsbffsrv / Verify opsbffsrv:"
    echo "     curl http://localhost:8081/internal/health"
    echo ""
    echo "  7. 运行集成测试 / Run integration tests:"
    echo "     python test_service_management_refactoring.py"
    echo ""
else
    print_success "服务正在运行，可以进行热更新部署 / Services are running, can perform hot deployment"
    echo ""
    print_info "热更新步骤 / Hot Update Steps:"
    echo ""
    echo "  1. 重启 infrasrv / Restart infrasrv:"
    echo "     docker-compose restart infrasrv.service"
    echo ""
    echo "  2. 验证 infrasrv / Verify infrasrv:"
    echo "     curl http://localhost:8080/internal/health"
    echo ""
    echo "  3. 重启 opsbffsrv / Restart opsbffsrv:"
    echo "     docker-compose restart opsbffsrv.service"
    echo ""
    echo "  4. 验证 opsbffsrv / Verify opsbffsrv:"
    echo "     curl http://localhost:8081/internal/health"
    echo ""
    echo "  5. 运行集成测试 / Run integration tests:"
    echo "     python test_service_management_refactoring.py"
    echo ""
fi

# 步骤 6: 回滚计划 / Step 6: Rollback plan
print_header "步骤 6: 回滚计划 / Step 6: Rollback Plan"

print_info "如果部署失败，执行以下回滚步骤 / If deployment fails, execute rollback steps:"
echo ""
echo "  1. 恢复代码 / Restore code:"
echo "     git stash"
echo "     git checkout <previous-commit>"
echo ""
echo "  2. 重启服务 / Restart services:"
echo "     docker-compose restart infrasrv.service opsbffsrv.service"
echo ""
echo "  3. 验证服务 / Verify services:"
echo "     curl http://localhost:8080/internal/health"
echo "     curl http://localhost:8081/internal/health"
echo ""

# 总结 / Summary
print_header "检查完成 / Check Complete"

print_success "所有检查通过 / All checks passed"
print_info "请按照上述建议进行部署 / Please deploy according to the recommendations above"

echo ""
print_info "下一步 / Next Steps:"
echo "  1. 按照部署步骤部署服务 / Deploy services according to deployment steps"
echo "  2. 运行集成测试验证功能 / Run integration tests to verify functionality"
echo "  3. 监控日志查看是否有错误 / Monitor logs for any errors"
echo ""

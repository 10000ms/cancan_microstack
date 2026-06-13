#!/bin/bash
# 检查所有数据库表是否正确创建
# 用于验证数据库初始化是否完整

echo "======================================"
echo "检查所有数据库表"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查数据库是否存在
echo "1. 检查数据库是否存在"
echo "-----------------------------------"
databases=$(podman exec my_app_postgres psql -U postgres -t -c "SELECT datname FROM pg_database WHERE datname IN ('main', 'infra', 'ops', 'biz');")
for db in main infra ops biz; do
    if echo "$databases" | grep -q "$db"; then
        echo -e "  ${GREEN}✓${NC} Database: $db"
    else
        echo -e "  ${RED}✗${NC} Database: $db (不存在)"
    fi
done
echo ""

# 检查 infra 数据库的表
echo "2. 检查 infra 数据库的表"
echo "-----------------------------------"
expected_infra_tables=(
    "service_info_tbl"
    "service_config_tbl"
    "service_action_log_tbl"
)
infra_tables=$(podman exec my_app_postgres psql -U postgres -d infra -t -c "\dt" | awk '{print $3}' | grep -v "^$")
for table in "${expected_infra_tables[@]}"; do
    if echo "$infra_tables" | grep -q "^$table$"; then
        echo -e "  ${GREEN}✓${NC} infra.$table"
    else
        echo -e "  ${RED}✗${NC} infra.$table (不存在)"
    fi
done
echo ""

# 检查 ops 数据库的表
echo "3. 检查 ops 数据库的表"
echo "-----------------------------------"
expected_ops_tables=(
    "caddy_access_log_tbl"
    "caddy_certificate_tbl"
    "caddy_rate_limit_tbl"
    "caddy_route_tbl"
    "caddy_stats_tbl"
)
ops_tables=$(podman exec my_app_postgres psql -U postgres -d ops -t -c "\dt" | awk '{print $3}' | grep -v "^$")
for table in "${expected_ops_tables[@]}"; do
    if echo "$ops_tables" | grep -q "^$table$"; then
        echo -e "  ${GREEN}✓${NC} ops.$table"
    else
        echo -e "  ${RED}✗${NC} ops.$table (不存在)"
    fi
done
echo ""

# 检查 biz 数据库的表
echo "4. 检查 biz 数据库的表"
echo "-----------------------------------"
expected_biz_tables=(
    "k_line_data_tbl"
    "k_line_current_data_tbl"
    "tech_article_tbl"
)
biz_tables=$(podman exec my_app_postgres psql -U postgres -d biz -t -c "\dt" | awk '{print $3}' | grep -v "^$")
for table in "${expected_biz_tables[@]}"; do
    if echo "$biz_tables" | grep -q "^$table$"; then
        echo -e "  ${GREEN}✓${NC} biz.$table"
    else
        echo -e "  ${RED}✗${NC} biz.$table (不存在)"
    fi
done
echo ""

# 检查触发器函数是否存在
echo "5. 检查触发器函数"
echo "-----------------------------------"
trigger_functions=("update_modified_column" "upd_timestamp")
for db in infra ops biz; do
    echo "  检查 $db 数据库的触发器函数："
    functions=$(podman exec my_app_postgres psql -U postgres -d $db -t -c "SELECT proname FROM pg_proc WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public') AND proname IN ('update_modified_column', 'upd_timestamp');")
    for func in "${trigger_functions[@]}"; do
        if echo "$functions" | grep -q "$func"; then
            echo -e "    ${GREEN}✓${NC} $func"
        else
            echo -e "    ${YELLOW}⚠${NC} $func (不存在，某些表可能需要此函数)"
        fi
    done
done
echo ""

echo "======================================"
echo "检查完成"
echo "======================================"

#!/bin/bash
# Caddy 快速启动脚本

set -e

echo "=========================================="
echo "  Caddy with Coraza WAF - 快速启动"
echo "=========================================="
echo ""

# 检查必要的目录
echo "[1/5] 检查目录结构..."
mkdir -p caddy/logs
mkdir -p caddy/data
mkdir -p caddy/config
mkdir -p caddy/geoip
mkdir -p caddy/waf
echo "✓ 目录结构检查完成"
echo ""

# 下载 GeoIP 数据库（可选）
echo "[2/5] 检查 GeoIP 数据库..."
if [ ! -f "caddy/geoip/GeoLite2-City.mmdb" ]; then
    echo "⚠️  GeoLite2-City.mmdb 不存在"
    echo "   请手动下载并放置到 caddy/geoip/ 目录"
    echo "   下载地址: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data"
else
    echo "✓ GeoIP 数据库已存在"
fi
echo ""

# 构建 Caddy 镜像
echo "[3/5] 构建 Caddy 镜像（包含 Coraza WAF）..."
docker-compose build caddy.service
echo "✓ Caddy 镜像构建完成"
echo ""

# 启动服务
echo "[4/5] 启动 Caddy 服务..."
docker-compose up -d caddy.service
echo "✓ Caddy 服务启动成功"
echo ""

# 等待服务就绪
echo "[5/5] 等待 Caddy 就绪..."
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "caddy.service.*Up"; then
    echo "✓ Caddy 运行正常"
else
    echo "✗ Caddy 启动失败，请查看日志："
    echo "  docker-compose logs caddy.service"
    exit 1
fi
echo ""

echo "=========================================="
echo "  Caddy 启动完成！"
echo "=========================================="
echo ""
echo "服务访问地址："
echo "  - HTTP:  http://localhost"
echo "  - HTTPS: https://localhost"
echo "  - Admin API: http://localhost:2019"
echo ""
echo "查看日志："
echo "  - Caddy 日志:      docker-compose logs -f caddy.service"
echo "  - WAF 审计日志:    docker exec my_app_caddy tail -f /var/log/caddy/waf-audit.log"
echo "  - WAF 调试日志:    docker exec my_app_caddy tail -f /var/log/caddy/waf-debug.log"
echo ""
echo "测试 WAF 防护："
echo "  - SQL 注入测试:    curl \"http://localhost/v1/besrv/api?id=1' OR '1'='1\""
echo "  - XSS 测试:        curl \"http://localhost/v1/besrv/api?name=<script>alert(1)</script>\""
echo "  - 路径遍历测试:    curl \"http://localhost/.env\""
echo ""
echo "更多信息请查看: caddy/README.md"
echo ""

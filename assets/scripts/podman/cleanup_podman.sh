#!/bin/bash

# Podman 清理脚本
# 用于清理所有 my_app 相关的容器和资源

echo "========================================="
echo "清理 Podman 容器"
echo "========================================="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 停止并删除所有 my_app 容器（忽略错误）
echo "正在停止并删除容器..."
podman stop my_app_caddy my_app_infrasrv my_app_opsbffsrv my_app_besrv my_app_postgres my_app_redis 2>/dev/null || true

podman rm my_app_caddy my_app_infrasrv my_app_opsbffsrv my_app_besrv my_app_postgres my_app_redis 2>/dev/null || true

echo ""
echo "✅ 容器清理完成"
echo ""

# 显示剩余的 my_app 容器（如果有）
echo "剩余的 my_app 容器:"
podman ps -a --filter "name=my_app" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "  无"
echo ""

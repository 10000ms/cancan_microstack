#!/bin/bash

# 容器环境检测脚本
# 自动检测当前系统的容器引擎和 Compose 工具

echo "========================================="
echo "容器环境检测"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检测 Docker
echo "检测 Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version 2>&1)
    echo -e "${GREEN}✓ Docker 已安装:${NC} $DOCKER_VERSION"
    
    if docker info > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Docker 运行正常${NC}"
    else
        echo -e "${YELLOW}⚠ Docker 未运行${NC}"
    fi
    
    # 检测 docker-compose
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_V1=$(docker-compose --version 2>&1)
        echo -e "${GREEN}✓ docker-compose 已安装:${NC} $DOCKER_COMPOSE_V1"
    else
        echo -e "${YELLOW}⚠ docker-compose (v1) 未安装${NC}"
    fi
    
    # 检测 docker compose
    if docker compose version > /dev/null 2>&1; then
        DOCKER_COMPOSE_V2=$(docker compose version 2>&1)
        echo -e "${GREEN}✓ docker compose 已安装:${NC} $DOCKER_COMPOSE_V2"
    else
        echo -e "${YELLOW}⚠ docker compose (v2) 未安装${NC}"
    fi
else
    echo -e "${RED}✗ Docker 未安装${NC}"
fi

echo ""
echo "========================================="
echo ""

# 检测 Podman
echo "检测 Podman..."
if command -v podman &> /dev/null; then
    PODMAN_VERSION=$(podman --version 2>&1)
    echo -e "${GREEN}✓ Podman 已安装:${NC} $PODMAN_VERSION"
    
    if podman info > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Podman 运行正常${NC}"
        
        # macOS 上检测 Podman Machine
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if podman machine list > /dev/null 2>&1; then
                echo ""
                echo "Podman Machine 状态:"
                podman machine list
            fi
        fi
    else
        echo -e "${YELLOW}⚠ Podman 未运行${NC}"
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo ""
            echo "macOS 用户请启动 Podman Machine:"
            echo "  podman machine init --cpus 4 --memory 8192 --disk-size 50"
            echo "  podman machine start"
        else
            echo ""
            echo "请检查 Podman 服务状态:"
            echo "  sudo systemctl status podman"
        fi
    fi
    
    # 检测 podman-compose
    if command -v podman-compose &> /dev/null; then
        PODMAN_COMPOSE=$(podman-compose --version 2>&1)
        echo -e "${GREEN}✓ podman-compose 已安装:${NC} $PODMAN_COMPOSE"
    else
        echo -e "${YELLOW}⚠ podman-compose 未安装${NC}"
        echo "  安装命令: pip install podman-compose"
    fi
    
    # 检测 podman compose (内置)
    if podman compose version > /dev/null 2>&1; then
        PODMAN_COMPOSE_BUILTIN=$(podman compose version 2>&1)
        echo -e "${GREEN}✓ podman compose 可用:${NC} $PODMAN_COMPOSE_BUILTIN"
    else
        echo -e "${YELLOW}⚠ podman compose (内置) 不可用${NC}"
    fi
else
    echo -e "${RED}✗ Podman 未安装${NC}"
    echo ""
    echo "安装 Podman:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  macOS: brew install podman"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "  Linux: 参考 https://podman.io/getting-started/installation"
    fi
fi

echo ""
echo "========================================="
echo "推荐配置"
echo "========================================="
echo ""

# 判断推荐使用什么
if command -v podman &> /dev/null && podman info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 推荐使用 Podman 环境${NC}"
    echo ""
    echo "启动脚本:"
    echo "  ./start_podman.sh          - 启动 controllersrv"
    echo "  ./start_compose_podman.sh  - 启动 Podman Compose 集群"
    echo "  ./start_all_podman.sh      - 一键启动所有服务"
    echo ""
    echo "停止脚本:"
    echo "  ./stop.sh                  - 停止 controllersrv"
    echo "  ./stop_compose_podman.sh   - 停止 Podman Compose 集群"
    echo "  ./stop_all_podman.sh       - 一键停止所有服务"
elif command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 推荐使用 Docker 环境${NC}"
    echo ""
    echo "启动脚本:"
    echo "  ./start.sh          - 启动 controllersrv"
    echo "  ./start_compose.sh  - 启动 Docker Compose 集群"
    echo "  ./start_all.sh      - 一键启动所有服务"
    echo ""
    echo "停止脚本:"
    echo "  ./stop.sh           - 停止 controllersrv"
    echo "  ./stop_compose.sh   - 停止 Docker Compose 集群"
    echo "  ./stop_all.sh       - 一键停止所有服务"
else
    echo -e "${RED}✗ 未检测到可用的容器环境${NC}"
    echo ""
    echo "请安装 Docker 或 Podman："
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Docker:  https://www.docker.com/products/docker-desktop"
        echo "  Podman:  brew install podman"
    fi
fi

echo ""
echo "========================================="
echo "Python 环境检测"
echo "========================================="
echo ""

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓ Python3 已安装:${NC} $PYTHON_VERSION"
else
    echo -e "${RED}✗ Python3 未安装${NC}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${GREEN}✓ 虚拟环境存在:${NC} $PROJECT_ROOT/venv"
else
    echo -e "${YELLOW}⚠ 虚拟环境不存在${NC}"
    echo "  创建命令: python3 -m venv venv"
    echo "  激活命令: source venv/bin/activate"
    echo "  安装依赖: pip install -r requirements.txt"
fi

echo ""

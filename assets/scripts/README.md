# Scripts 目录

本目录包含项目的所有管理脚本，按功能分类组织。

## 目录结构

```
scripts/
├── docker/           # Docker Compose 相关脚本
├── podman/           # Podman Compose 相关脚本
├── dev/              # 开发环境相关脚本
└── utils/            # 工具类脚本
```

## Docker 脚本 (`docker/`)

Docker Compose 环境的服务管理脚本。

### 完整环境管理
- `start_all.sh` - 一键启动 controllersrv 和所有 Docker Compose 服务
- `stop_all.sh` - 一键停止所有服务（包括 controllersrv 和 Docker Compose）

### controllersrv 管理
- `start.sh` - 启动 controllersrv（宿主机运行）
- `stop.sh` - 停止 controllersrv
- `restart.sh` - 重启 controllersrv

### Docker Compose 集群管理
- `start_compose.sh` - 启动 Docker Compose 集群（infrasrv, opsbffsrv, besrv）
- `stop_compose.sh` - 停止 Docker Compose 集群
- `restart_compose.sh` - 重启 Docker Compose 集群

### 使用示例

```bash
# 开发环境快速启动
./scripts/docker/start_all.sh

# 重启单个服务
docker-compose restart infrasrv

# 查看日志
docker-compose logs -f infrasrv

# 停止所有服务
./scripts/docker/stop_all.sh
```

## Podman 脚本 (`podman/`)

Podman Compose 环境的服务管理脚本（功能与 Docker 脚本对应）。

### 完整环境管理
- `start_all_podman.sh` - 一键启动 controllersrv 和所有 Podman Compose 服务
- `stop_all_podman.sh` - 一键停止所有服务

### controllersrv 管理
- `start_podman.sh` - 启动 controllersrv（Podman 环境）

### Podman Compose 集群管理
- `start_compose_podman.sh` - 启动 Podman Compose 集群
- `stop_compose_podman.sh` - 停止 Podman Compose 集群
- `restart_compose_podman.sh` - 重启 Podman Compose 集群

### 使用示例

```bash
# 开发环境快速启动
./scripts/podman/start_all_podman.sh

# 重启单个服务
podman-compose restart infrasrv

# 查看日志
podman-compose logs -f infrasrv

# 停止所有服务
./scripts/podman/stop_all_podman.sh
```

## 开发环境脚本 (`dev/`)

本地开发环境的特殊脚本。

### Out Pod 开发模式
- `start_dev_out_pod.sh` - 启动 Out Pod 开发环境（仅 PostgreSQL + Redis）
- `stop_dev_out_pod.sh` - 停止 Out Pod 开发环境

Out Pod 模式适用于：
- 需要在 IDE 中调试 Python 代码
- 需要频繁修改代码并快速测试
- 不需要完整的容器化环境

### 使用示例

```bash
# 1. 启动基础设施（PostgreSQL + Redis）
./scripts/dev/start_dev_out_pod.sh

# 2. 在宿主机运行服务
export NE_CONFIG=dev_out_pod
python cmd/infrasrv/run.py

# 3. 停止基础设施
./scripts/dev/stop_dev_out_pod.sh
```

## 工具脚本 (`utils/`)

通用工具类脚本。

- `check_env.sh` - 检查当前容器引擎环境（Docker 或 Podman）

### 使用示例

```bash
# 检查环境
./scripts/utils/check_env.sh
# 输出: Using Docker Compose (version 2)
# 或: Using podman-compose
```

## 环境模式说明

项目支持 3 种环境模式（通过 `NE_CONFIG` 环境变量控制）：

### 1. `dev_in_pod` - 容器内开发
- 所有服务运行在 Docker/Podman 容器中
- 代码通过 volume 挂载实现热更新
- 适合完整的容器化开发和测试
- **使用脚本**: `docker/start_all.sh` 或 `podman/start_all_podman.sh`

```bash
export NE_CONFIG=dev_in_pod
./scripts/docker/start_all.sh
```

### 2. `dev_out_pod` - 容器外开发
- 只运行 PostgreSQL 和 Redis 容器
- 业务服务在宿主机运行
- 适合需要 IDE 调试的场景
- **使用脚本**: `dev/start_dev_out_pod.sh`

```bash
export NE_CONFIG=dev_out_pod
./scripts/dev/start_dev_out_pod.sh
python cmd/infrasrv/run.py
```

### 3. `prod` - 生产环境
- 完整的生产配置
- 所有服务容器化部署
- **使用脚本**: `docker/start_all.sh`（配置不同）

```bash
export NE_CONFIG=prod
./scripts/docker/start_all.sh
```

## 脚本执行权限

所有脚本默认已设置执行权限：

```bash
chmod +x scripts/**/*.sh
```

## 故障排查

### Docker/Podman 检测失败
运行环境检测脚本：
```bash
./scripts/utils/check_env.sh
```

### 服务启动失败
查看详细日志：
```bash
docker-compose logs -f <service_name>
# 或
podman-compose logs -f <service_name>
```

### controllersrv 无法连接
确认 controllersrv 已启动：
```bash
curl http://localhost:22100/internal/health
```

## 相关文档

- [快速开始指南](../docs/guides/QUICK_START.md)
- [Docker Compose 使用指南](../docs/guides/DOCKER_COMPOSE_USAGE.md)
- [Podman 快速上手](../docs/guides/PODMAN_QUICKSTART.md)
- [服务注册说明](../docs/guides/SERVICE_REGISTRY_README.md)

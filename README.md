# Cancan Microstack

[![PyPI](https://img.shields.io/pypi/v/cancan-microstack.svg?color=8b7cff)](https://pypi.org/project/cancan-microstack/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

可嵌入的基础设施微服务栈：把一整套基础设施微服务（`controllersrv` / `infrasrv` / `opsbffsrv`）连同 Docker Compose 编排、DDL、运维前端与统一 CLI，打包成**一个可 pip 安装的 Python 库**，让业务仓库“只写业务代码”。

An embeddable infrastructure microstack: bundle a complete set of infrastructure microservices (`controllersrv` / `infrasrv` / `opsbffsrv`) — together with Docker Compose orchestration, DDL, an ops UI and a unified CLI — into **a single pip-installable Python library**, so your product repo contains business logic only.

> 📖 **完整文档 / Full documentation**：[`docs/index.html`](docs/index.html) — 双语、含架构原理、CLI 参考与使用说明。
> Bilingual docs with architecture, CLI reference and guides.

> **定位 / Positioning**：本库只包含**通用基础设施能力**；具体业务服务与逻辑应留在你自己的业务仓库。
> This library contains **generic infrastructure capabilities only**; your business services and logic stay in your own product repo.

## 特性 / Features

- 🛠️ **统一 CLI / Unified CLI**：`cancan` 命令提供 `assets` / `compose` / `services` / `stack` 子命令。
- 🔀 **Compose 构建器 / Compose builder**：把内置 infra compose 与业务 compose、override 深度合并成一个可运行栈。
  Deep-merge the built-in infra compose with your services compose and overrides into one runnable stack.
- 🔌 **免 Fork 覆盖 / Fork-free overrides**：用 `cancan_overrides/` 只替换你想改的文件，其余复用库实现。
- 🖥️ **内置运维前端 / Bundled ops UI**：随库附带 adminops UI 构建产物，可导出由 Caddy 挂载。
- 🗄️ **自管理 DDL / Self-managed DDL**：infra/ops 数据库表随服务启动自动初始化。
- ♻️ **整栈生命周期 / Full-stack lifecycle**：`stack up/down/status` 同时管理宿主机进程与容器栈。

构建于已发布的姊妹库之上 / Built on published sibling libraries：[`linglong-web`](https://pypi.org/project/linglong-web/) · [`dragonfly-container`](https://pypi.org/project/dragonfly-container/)。

## 快速开始 / Quick Start

```bash
# 1. 安装 / Install
pip install cancan-microstack

# 2. 脚手架：生成最小可跑工作区（业务 compose 样例 + .env + overrides 骨架）
#    Scaffold a minimal workspace (services compose sample + .env + overrides skeleton)
cancan init

# 3. 预检环境（容器引擎 / 端口 / 配置 / 弱默认值）
#    Pre-flight checks (engine / ports / config / weak defaults)
cancan doctor

# 4. 一键启动整套集群（推荐）/ Bring up the whole stack
#    生成 compose.cancan.yml、bootstrap 运行文件、宿主机起 controllersrv、容器栈 up
cancan stack up --workspace . --service-file docker-compose.services.yml

# 5. 状态 / 关闭 — status / teardown
cancan stack status --workspace .
cancan stack down   --workspace .
```

> 安装即提供 `cancan` 命令；也可用 `python -m cancan_microstack.cli ...`。
> Installing provides the `cancan` command; `python -m cancan_microstack.cli ...` works too.
>
> 运行容器栈需要 Docker 或 Podman。 / Running the stack requires Docker or Podman.

> ⚠️ **生产安全 / Production safety**：凭据与密钥集中在工作区 `.env`（`cancan init` 会生成，并自动写入一个唯一的 TOTP 加密 key）。其中数据库等使用本地开发弱默认值（如 `admin123`）以便开箱即用。**生产部署务必在 `.env` 里改成真实凭证；`cancan doctor` 会提示仍在使用的弱默认值。**
> Credentials & secrets live in the workspace `.env` (created by `cancan init`, with a unique TOTP encryption key auto-generated). Databases use weak local-dev defaults (e.g. `admin123`) for out-of-the-box use. **In production, set real secrets in `.env`; `cancan doctor` flags any weak defaults still in use.**

## CLI 速览 / CLI at a glance

| 命令 / Command | 作用 / Purpose |
| --- | --- |
| `cancan init` | 脚手架最小可跑工作区 / scaffold a minimal runnable workspace |
| `cancan doctor` | 起栈前环境/配置预检 / pre-flight environment & config checks |
| `cancan assets list [subdir]` | 列出内置资产 / list bundled assets |
| `cancan assets export <name> <dest> [--overwrite]` | 导出资产到工作区 / export an asset to the workspace |
| `cancan compose build [--service-file …] [--override …]` | 合成 `compose.cancan.yml` / synthesize the stack file |
| `cancan services run <name> [--host] [--port]` | 前台运行内置服务 / run a bundled service in the foreground |
| `cancan stack up/down/status` | 整栈生命周期（宿主机进程 + 容器栈）/ full-stack lifecycle |

完整参数与原理见 [`docs/index.html`](docs/index.html)。 / Full options and design in the docs.

## 内置服务 / Bundled services

| 服务 / Service | 职责 / Responsibility |
| --- | --- |
| `controllersrv` | 宿主机进程，封装 Docker/Podman 容器操作（基于 `dragonfly-container`）/ host process managing containers |
| `infrasrv` | 服务注册、工作流引擎与调度、日志采集、健康检查 / registry, workflow, log ingestion, health checks |
| `opsbffsrv` | 运维 BFF：为 adminops 前端聚合接口（认证 / Caddy / DB / 日志）/ ops BFF for the admin UI |

服务配置基于 `linglong-web`，资源（PostgreSQL / Redis / MongoDB / RabbitMQ / Celery）由其统一编排。
Services are configured via `linglong-web`, which orchestrates the backing resources.

## 免 Fork 覆盖 / Fork-free overrides

在工作区放一个 `cancan_overrides/<service>/` 目录，只放你要替换的文件，运行时会优先加载它，其余仍复用库实现（也可用环境变量 `CANCAN_OVERRIDE_ROOT` 指定）。

Drop a `cancan_overrides/<service>/` directory in your workspace with only the files you want to replace; it is loaded with priority at runtime while the rest falls back to the library (or point at it via `CANCAN_OVERRIDE_ROOT`).

## 运维前端（adminops）/ The adminops UI

库内**只包含前端的构建产物**（`assets/www/adminops/`），不含前端源码。前端源码在独立仓库维护；更新流程：在前端源码仓构建（`pnpm build`）→ 把 `dist` 产物覆盖到 `assets/www/adminops/` → 重新发布本库。

This library ships **only the built frontend artifacts** (`assets/www/adminops/`), not the frontend source. The UI source lives in a separate repository; to update: build in the source repo (`pnpm build`) → copy the `dist` output into `assets/www/adminops/` → re-release this library.

## 开发 / Development

```bash
git clone https://github.com/10000ms/cancan_microstack.git
cd cancan_microstack
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## 许可证 / License

MIT License © 2026 Victor Lai

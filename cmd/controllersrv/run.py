"""
controllersrv 启动脚本

这是一个特殊的服务，运行在宿主机上，负责管理 Docker Compose 集群。

初始化流程：
1. 初始化路由
2. 初始化服务，挂载启动和关闭回调
3. 启动服务

启动回调 (`initialize_controllersrv`):
1. 初始化服务验证器
2. 初始化执行器
3. 初始化并启动 Worker

关闭回调 (`shutdown_controllersrv`):
1. 优雅关闭 Worker
"""
import asyncio
import os
from typing import Optional

from linglong_web.utils import logger
from linglong_web import ServerRouter
from linglong_web import LinglongConfig
from dragonfly_container.core import ExecutorFactory
from dragonfly_container.models.constants import ContainerEngine

from cancan_microstack.public.web.server import AppServer

from cancan_microstack.services.controllersrv.router import router_list
from cancan_microstack.services.controllersrv.conf.config import service_conf_dict
from cancan_microstack.services.controllersrv.domain.task import TaskWorker, set_task_worker
from cancan_microstack.services.controllersrv.domain.service_validator import init_service_validator

worker_instance: Optional[TaskWorker] = None


async def initialize_controllersrv():
    """
    controllersrv 的启动回调函数（直接使用 Dragonfly Container UnifiedExecutor）
    """
    global worker_instance
    logger.info("=" * 60)
    logger.info("Starting controllersrv initialization")
    logger.info("=" * 60)

    # 1. 创建 UnifiedExecutor（自动检测 Docker 或 Podman）
    # Create UnifiedExecutor (auto-detect Docker or Podman)
    logger.info("Step 1: Creating Dragonfly Container UnifiedExecutor...")
    compose_file = LinglongConfig.DOCKER_COMPOSE_FILE
    project_name = LinglongConfig.DOCKER_COMPOSE_PROJECT_NAME
    # engine 选择：默认 Docker-first auto-detect 可能在 macOS 上导致慢启动（Docker 未运行时会卡住）。
    # Engine selection: Docker-first auto-detect may cause slow startup on macOS when Docker isn't running.
    engine_env = (os.environ.get("CANCAN_CONTAINER_ENGINE") or "").strip().lower()
    engine: ContainerEngine | None = None
    if engine_env in {"podman"}:
        engine = ContainerEngine.PODMAN
    elif engine_env in {"docker"}:
        engine = ContainerEngine.DOCKER

    executor = ExecutorFactory.create_unified_executor(
        compose_file=compose_file,
        project_name=project_name,
        engine=engine,
    )
    logger.info(
        f"UnifiedExecutor created: "
        f"engine={executor.api.engine_type}, "
        f"compose_file={compose_file}, "
        f"project={project_name}"
    )

    # 2. 初始化服务验证器（传入 executor 以便使用其 API）
    # Initialize service validator (pass executor to use its API)
    logger.info("Step 2: Initializing service validator...")
    init_service_validator(compose_file, executor)
    logger.info(f"Service validator initialized with compose file: {compose_file}")

    # 3. 初始化并启动 Worker（直接使用 UnifiedExecutor）
    logger.info("Step 3: Starting task worker...")
    worker = TaskWorker(executor)
    worker_instance = worker
    set_task_worker(worker)
    await worker.start()
    logger.info("Task worker started")

    logger.info("=" * 60)
    logger.info("controllersrv initialization completed")
    logger.info("=" * 60)


async def shutdown_controllersrv():
    """
    controllersrv 的关闭回调函数
    """
    if worker_instance:
        logger.info("Shutting down task worker...")
        await worker_instance.stop()
        logger.info("Task worker stopped")


async def main(host='0.0.0.0', port=22100):
    """
    启动 controllersrv 服务
    
    Args:
        host: 监听地址，默认 0.0.0.0（允许容器访问）
        port: 监听端口，默认 22100
    """
    # 1. 初始化路由
    router_factory = ServerRouter()
    router_factory.initialize(router_list)

    # 2. 初始化服务器
    app = AppServer()
    await app.initialize(
        service_name="controllersrv",
        router=router_factory.get_router(),
        config_dict=service_conf_dict,
        scheduler_group=None,  # controllersrv 不需要定时任务
        on_startup=[initialize_controllersrv],
        on_shutdown=[shutdown_controllersrv],
    )

    # 3. 启动 Web 服务
    await app.start(host=host, port=port)


if __name__ == "__main__":
    asyncio.run(main())

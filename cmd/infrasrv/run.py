"""infrasrv startup entrypoint.

用于容器内启动 infrasrv 服务（被 cmd/infrasrv/run.py 包装器调用）。
Start infrasrv inside container (called by workspace cmd wrapper).
"""

import asyncio

from linglong_web import ServerRouter
from linglong_web.utils import logger

from cancan_microstack.public.web.server import AppServer
from cancan_microstack.services.infrasrv.application.logging.log_ingestion_service import get_log_ingestion_service
from cancan_microstack.services.infrasrv.application.workflow.workflow_tasks import register_workflow_tasks
from cancan_microstack.services.infrasrv.application.workflow.workflow_worker_runtime import (
    start_inline_worker,
    stop_inline_worker,
)
from cancan_microstack.services.infrasrv.conf.config import service_conf_dict
from cancan_microstack.services.infrasrv.domain.hooks import get_hook_manager
from cancan_microstack.services.infrasrv.domain.hooks.builtin_hooks import register_default_hooks
from cancan_microstack.services.infrasrv.infrastructure.ddl_manager import init_ddl
from cancan_microstack.services.infrasrv.interface.schedule.scheduler import scheduler_group
from cancan_microstack.services.infrasrv.router import router_list


async def initialize_infrasrv() -> None:
    """infrasrv 的启动回调函数 / Startup callback for infrasrv."""

    # DDL 自管理：检查并创建 infra 表
    # DDL auto-init: check and create infra tables
    logger.info("Checking and initializing infra tables...")
    ddl_success = await init_ddl()
    if not ddl_success:
        logger.warning("DDL initialization failed, but continuing to start service...")

    # 初始化预注册钩子
    # Initialize pre-registration hooks
    logger.info("Initializing pre-registration hooks...")
    hook_manager = get_hook_manager()
    register_default_hooks(hook_manager)
    logger.info(f"Registered {len(hook_manager.get_hooks('pre_register'))} pre-registration hooks")


async def register_workflow_tasks_on_startup() -> None:
    """在服务启动阶段注册所有工作流任务 / Register workflow tasks during startup."""

    register_workflow_tasks()
    start_inline_worker()


async def start_log_ingestion() -> None:
    """启动日志消费服务 / Start log ingestion service."""

    log_ingestion_service = get_log_ingestion_service()
    await log_ingestion_service.start()


async def stop_inline_worker_on_shutdown() -> None:
    """停止内嵌 worker，确保 infrasrv 退出前清理资源 / Stop inline worker on shutdown."""

    stop_inline_worker()


async def stop_log_ingestion() -> None:
    """停止日志消费服务 / Stop log ingestion service."""

    log_ingestion_service = get_log_ingestion_service()
    await log_ingestion_service.shutdown()


async def main(host: str = "0.0.0.0", port: int = 8080) -> None:
    """启动 infrasrv / Start infrasrv."""

    router_factory = ServerRouter()
    router_factory.initialize(router_list)

    app = AppServer()

    await app.initialize(
        service_name="infrasrv",
        router=router_factory.get_router(),
        config_dict=service_conf_dict,
        scheduler_group=scheduler_group,
        on_startup=[
            initialize_infrasrv,
            start_log_ingestion,
            register_workflow_tasks_on_startup,
        ],
        on_shutdown=[
            stop_log_ingestion,
            stop_inline_worker_on_shutdown,
        ],
    )

    await app.start(host=host, port=port)


if __name__ == "__main__":
    asyncio.run(main())

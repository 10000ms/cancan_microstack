"""opsbffsrv startup entrypoint.

用于容器内启动 opsbffsrv 服务（被 cmd/opsbffsrv/run.py 包装器调用）。
Start opsbffsrv inside container (called by workspace cmd wrapper).
"""

import asyncio

from linglong_web import ServerRouter
from linglong_web.utils import logger

from cancan_microstack.public.web.server import AppServer
from cancan_microstack.services.opsbffsrv.application.caddy.access_log_ingestion_service import (
    get_caddy_access_log_ingestion_service,
)
from cancan_microstack.services.opsbffsrv.application.caddy.route_management_app import RouteManagementApp
from cancan_microstack.services.opsbffsrv.conf.config import service_conf_dict, validate_auth_config
from cancan_microstack.services.opsbffsrv.domain.auth.admin_init import ensure_admin_user
from cancan_microstack.services.opsbffsrv.domain.caddy.default_routes import init_default_routes
from cancan_microstack.services.opsbffsrv.infrastructure.ddl_manager import init_ddl
from cancan_microstack.services.opsbffsrv.interface.middleware.auth_middleware import auth_middleware
from cancan_microstack.services.opsbffsrv.router import router_list


async def initialize_opsbffsrv() -> None:
    """opsbffsrv 的启动回调函数 / Startup callback for opsbffsrv."""

    # 认证关键配置 fail-fast 校验（生产缺 Fernet key 直接拒绝启动）。
    # Fail-fast validation of auth-critical config (refuse to start in prod without Fernet key).
    validate_auth_config()

    # DDL 自管理：检查并创建 ops 表
    # DDL auto-init: check and create ops tables
    logger.info("Checking and initializing ops tables...")
    ddl_success = await init_ddl()
    if not ddl_success:
        logger.warning("DDL initialization failed, but continuing to start service...")

    # 初始化 admin 用户
    # Initialize admin user
    logger.info("Checking and initializing admin user...")
    await ensure_admin_user()

    # 初始化默认路由
    # Initialize default routes
    await init_default_routes()

    # 同步路由到 Caddy
    # Sync routes to Caddy on startup
    logger.info("Syncing routes to Caddy on startup...")
    route_app = RouteManagementApp()
    sync_result = await route_app.sync_all_routes()
    if sync_result.get("status") != "success":
        # Caddy may be intentionally not started in some dev flows.
        # Some environments start opsbffsrv before caddy, so treat this as non-fatal.
        logger.warning("Sync routes to Caddy on startup skipped/failed: %s", sync_result)
    else:
        logger.info("Routes synced to Caddy successfully.")

    # 启动 Caddy 访问日志采集服务
    # Start Caddy access log ingestion service
    ingestion_service = get_caddy_access_log_ingestion_service()
    await ingestion_service.start()


async def shutdown_opsbffsrv() -> None:
    """opsbffsrv 的关闭回调函数 / Shutdown callback for opsbffsrv."""
    ingestion_service = get_caddy_access_log_ingestion_service()
    await ingestion_service.shutdown()


async def main(host: str = "0.0.0.0", port: int = 8080) -> None:
    """启动 opsbffsrv / Start opsbffsrv."""

    router_factory = ServerRouter()
    router_factory.initialize(router_list)

    app = AppServer()

    await app.initialize(
        service_name="opsbffsrv",
        router=router_factory.get_router(),
        config_dict=service_conf_dict,
        on_startup=[initialize_opsbffsrv],
        on_shutdown=[shutdown_opsbffsrv],
    )

    # 注册认证中间件
    # Register authentication middleware
    app.app.middleware("http")(auth_middleware)

    await app.start(host=host, port=port)


if __name__ == "__main__":
    asyncio.run(main())

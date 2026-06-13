"""
Default Caddy routes initialization module
"""
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyRouteCreate
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_route import (
    get_route_by_name,
    create_route,
)

DEFAULT_ROUTES = [
    CaddyRouteCreate(
        route_name="opsbffsrv-internal",
        domain="*",
        path_pattern="/v1/opsbffsrv/*",
        upstream_service="opsbffsrv",
        upstream_host="opsbffsrv.service",
        upstream_port=8080,
        priority=1000,
        is_enabled=True,
        enable_https=False,
        force_https=False,
        enable_waf=False,
        waf_rule_set="default",
        load_balance_strategy="round_robin",
        health_check_path=None,
        health_check_interval=30,
        strip_path_prefix=None,
        add_path_prefix=None,
        route_metadata=None,
        description="Internal route for opsbffsrv"
    ),
]


async def init_default_routes():
    """
    Initialize default Caddy routes if they don't exist
    """
    logger.info("Initializing default Caddy routes...")

    for route in DEFAULT_ROUTES:
        try:
            existing = await get_route_by_name(route.route_name)
            if not existing:
                logger.info(f"Creating default route: {route.route_name}")
                await create_route(route)
            else:
                logger.debug(f"Default route already exists: {route.route_name}")
        except Exception as e:
            logger.error(f"Failed to initialize default route {route.route_name}: {e}")

    logger.info("Default Caddy routes initialization completed")

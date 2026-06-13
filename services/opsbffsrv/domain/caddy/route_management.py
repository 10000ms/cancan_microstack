"""
Caddy 路由管理领域服务
包含路由配置的核心业务逻辑和业务规则
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyRoute, CaddyRouteCreate
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_route import (
    get_route_by_id,
    get_route_by_name,
    get_routes_by_domain,
    get_routes_by_service,
    get_enabled_routes,
    get_all_routes,
    create_route,
    update_route,
    update_route_by_name,
    enable_route,
    disable_route,
    delete_route,
    delete_route_by_name,
    count_routes,
)
from cancan_microstack.services.opsbffsrv.infrastructure.caddy.admin_api_client import caddy_admin_client


class RouteManagementDomain:
    """路由管理领域服务"""

    async def create_new_route(self, route: CaddyRouteCreate) -> CaddyRoute:
        """
        创建新路由
        
        业务规则：
        1. 路由名称必须唯一
        2. 优先级范围：0-1000
        3. 创建后自动同步到 Caddy
        
        Args:
            route: 路由创建对象
            
        Returns:
            创建后的路由对象
            
        Raises:
            ValueError: 业务规则违反
        """
        logger.info(f"Creating new route: {route.route_name}")

        # 业务规则验证
        await self._validate_route_create(route)

        # 创建数据库记录
        db_route = await create_route(route)
        logger.info(f"Route created in database: {db_route.id}")

        return db_route

    async def update_existing_route(self, route_id: int, data: Dict[str, Any]) -> Optional[CaddyRoute]:
        """
        更新现有路由
        
        Args:
            route_id: 路由 ID
            data: 更新数据
            
        Returns:
            更新后的路由对象或 None
        """
        logger.info(f"Updating route: {route_id}")

        # 验证路由存在
        existing_route = await get_route_by_id(route_id)
        if not existing_route:
            logger.warning(f"Route not found: {route_id}")
            return None

        # 更新数据库记录
        updated_route = await update_route(route_id, data)

        if updated_route:
            logger.info(f"Route updated: {route_id}")

        return updated_route

    async def toggle_route_status(self, route_id: int, enabled: bool) -> Optional[CaddyRoute]:
        """
        切换路由启用状态
        
        Args:
            route_id: 路由 ID
            enabled: 是否启用
            
        Returns:
            更新后的路由对象或 None
        """
        logger.info(f"Toggling route {route_id} status to: {enabled}")

        if enabled:
            updated_route = await enable_route(route_id)
        else:
            updated_route = await disable_route(route_id)

        return updated_route

    async def remove_route(self, route_id: int) -> bool:
        """
        删除路由
        
        Args:
            route_id: 路由 ID
            
        Returns:
            是否删除成功
        """
        logger.info(f"Removing route: {route_id}")

        # 验证路由存在
        existing_route = await get_route_by_id(route_id)
        if not existing_route:
            logger.warning(f"Route not found: {route_id}")
            return False

        # 删除数据库记录
        success = await delete_route(route_id)

        if success:
            logger.info(f"Route removed: {route_id}")

        return success

    async def get_route_details(self, route_id: int) -> Optional[CaddyRoute]:
        """
        获取路由详情
        
        Args:
            route_id: 路由 ID
            
        Returns:
            路由对象或 None
        """
        return await get_route_by_id(route_id)

    async def list_routes(self, filters: Optional[Dict[str, Any]] = None) -> List[CaddyRoute]:
        """
        列出路由
        
        Args:
            filters: 过滤条件
            
        Returns:
            路由列表
        """
        return await get_all_routes(filters)

    async def list_routes_by_domain(self, domain: str) -> List[CaddyRoute]:
        """
        按域名列出路由
        
        Args:
            domain: 域名
            
        Returns:
            路由列表
        """
        return await get_routes_by_domain(domain)

    async def list_routes_by_service(self, service: str) -> List[CaddyRoute]:
        """
        按服务列出路由
        
        Args:
            service: 服务名称
            
        Returns:
            路由列表
        """
        return await get_routes_by_service(service)

    async def sync_routes_to_caddy(self) -> bool:
        """
        将所有启用的路由同步到 Caddy
        
        Returns:
            是否同步成功
        """
        logger.info("Syncing routes to Caddy")

        # 获取所有启用的路由
        enabled_routes_list = await get_enabled_routes()

        if not enabled_routes_list:
            logger.warning("No enabled routes found, clearing all routes in Caddy")
            # Continue to sync empty list to clear routes
            # return False

        # 构建 Caddy 路由配置
        caddy_routes = []
        for route in enabled_routes_list:
            route_config = await caddy_admin_client.build_route_config(
                domain=route.domain,
                path_pattern=route.path_pattern,
                upstream_host=route.upstream_host,
                upstream_port=route.upstream_port,
                enable_https=route.enable_https,
                force_https=route.force_https,
                enable_waf=route.enable_waf,
                waf_rule_set=route.waf_rule_set,
                strip_path_prefix=route.strip_path_prefix,
                add_path_prefix=route.add_path_prefix,
            )
            caddy_routes.append(route_config)

        # 批量应用到 Caddy
        success = await caddy_admin_client.apply_routes_batch(caddy_routes)

        if success:
            logger.info(f"Successfully synced {len(caddy_routes)} routes to Caddy")
        else:
            logger.warning("Failed to sync routes to Caddy (Caddy may be unavailable)")

        return success

    async def _validate_route_create(self, route: CaddyRouteCreate):
        """
        验证路由创建的业务规则
        
        Args:
            route: 路由创建对象
            
        Raises:
            ValueError: 业务规则违反
        """
        # 验证路由名称唯一性
        existing_route = await get_route_by_name(route.route_name)
        if existing_route:
            raise ValueError(f"Route name already exists: {route.route_name}")

        # 验证优先级范围
        if route.priority < 0 or route.priority > 1000:
            raise ValueError(f"Priority must be between 0 and 1000: {route.priority}")

        # 验证上游端口范围
        if route.upstream_port < 1 or route.upstream_port > 65535:
            raise ValueError(f"Invalid upstream port: {route.upstream_port}")

        # 验证健康检查间隔
        if route.health_check_interval < 5:
            raise ValueError(f"Health check interval must be at least 5 seconds: {route.health_check_interval}")

    async def _validate_route_priority(self, priority: int):
        """
        验证路由优先级
        
        Args:
            priority: 优先级
            
        Raises:
            ValueError: 优先级无效
        """
        if priority < 0 or priority > 1000:
            raise ValueError(f"Priority must be between 0 and 1000: {priority}")

    async def get_route_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        获取路由数量
        
        Args:
            filters: 过滤条件
            
        Returns:
            路由数量
        """
        return await count_routes(filters)

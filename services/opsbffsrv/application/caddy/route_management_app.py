"""
Caddy 路由管理应用服务
协调路由管理的业务流程，包括路由同步到 Caddy
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from linglong_web.utils import logger

from cancan_microstack.public.schemas.caddy import (
    CaddyRoute,
    CaddyRouteCreate,
)
from cancan_microstack.services.opsbffsrv.domain.caddy.route_management import RouteManagementDomain


class RouteManagementApp:
    """路由管理应用服务"""

    def __init__(self):
        self.domain = RouteManagementDomain()

    def _extract_route_mutable_fields(self, route: CaddyRoute) -> Dict[str, Any]:
        """
        提取可写回数据库的路由字段，用于失败补偿回滚
        Extract mutable route fields for DB rollback compensation
        """
        route_data = route.model_dump()
        excluded_fields = {"id", "created_time", "update_time"}
        return {
            field: value
            for field, value in route_data.items()
            if field not in excluded_fields
        }

    async def _rollback_create_route(self, created_route: CaddyRoute) -> bool:
        """
        回滚创建操作：删除刚创建的路由记录
        Rollback create operation by deleting the newly created route
        """
        if created_route.id is None:
            logger.error("Rollback create failed: route id is missing")
            return False
        return await self.domain.remove_route(created_route.id)

    async def _rollback_update_route(self, route_id: int, previous_route: CaddyRoute) -> bool:
        """
        回滚更新/切换操作：恢复更新前字段
        Rollback update/toggle operation by restoring previous route fields
        """
        rollback_data = self._extract_route_mutable_fields(previous_route)
        rollback_result = await self.domain.update_existing_route(route_id, rollback_data)
        return rollback_result is not None

    async def _rollback_delete_route(self, deleted_route: CaddyRoute) -> bool:
        """
        回滚删除操作：重新插入被删除路由
        Rollback delete operation by recreating the deleted route
        """
        rollback_payload = CaddyRouteCreate.model_validate(
            self._extract_route_mutable_fields(deleted_route)
        )
        recreated_route = await self.domain.create_new_route(rollback_payload)
        return recreated_route is not None

    async def create_route_and_sync(self, route: CaddyRouteCreate) -> Dict[str, Any]:
        """
        创建路由并同步到 Caddy
        
        应用层职责：
        1. 调用领域层创建路由
        2. 如果启用，立即同步到 Caddy
        3. 返回结果和同步状态
        
        Args:
            route: 路由创建对象
            
        Returns:
            结果字典
        """
        logger.info(f"Creating and syncing route: {route.route_name}")

        try:
            # 创建路由
            created_route = await self.domain.create_new_route(route)

            # 如果路由启用，同步到 Caddy
            sync_success = True
            if created_route.is_enabled:
                sync_success = await self.domain.sync_routes_to_caddy()

            if not sync_success:
                rollback_success = await self._rollback_create_route(created_route)
                logger.warning(
                    "Create route sync failed, rollback create result: %s, route_id=%s",
                    rollback_success,
                    created_route.id,
                )
                return {
                    "status": "error",
                    "error": "Sync to Caddy failed, create rolled back" if rollback_success else (
                        "Sync to Caddy failed, and rollback failed"
                    ),
                    "synced_to_caddy": False,
                    "rollback_success": rollback_success,
                }

            return {
                "status": "success",
                "route": created_route,
                "synced_to_caddy": sync_success
            }
        except ValueError as e:
            logger.warning(f"Route creation failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error creating route: {e}", exc_info=True)
            return {
                "status": "error",
                "error": "Internal server error"
            }

    async def update_route_and_sync(self, route_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新路由并同步到 Caddy
        
        Args:
            route_id: 路由 ID
            data: 更新数据
            
        Returns:
            结果字典
        """
        logger.info(f"Updating and syncing route: {route_id}")

        try:
            previous_route = await self.domain.get_route_details(route_id)
            if not previous_route:
                return {
                    "status": "error",
                    "error": "Route not found"
                }

            # 更新路由
            updated_route = await self.domain.update_existing_route(route_id, data)

            if not updated_route:
                return {
                    "status": "error",
                    "error": "Route not found"
                }

            # 同步到 Caddy
            sync_success = await self.domain.sync_routes_to_caddy()

            if not sync_success:
                rollback_success = await self._rollback_update_route(route_id, previous_route)
                logger.warning(
                    "Update route sync failed, rollback update result: %s, route_id=%s",
                    rollback_success,
                    route_id,
                )
                return {
                    "status": "error",
                    "error": "Sync to Caddy failed, update rolled back" if rollback_success else (
                        "Sync to Caddy failed, and rollback failed"
                    ),
                    "synced_to_caddy": False,
                    "rollback_success": rollback_success,
                }

            return {
                "status": "success",
                "route": updated_route,
                "synced_to_caddy": sync_success
            }
        except Exception as e:
            logger.error(f"Error updating route: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def toggle_route_and_sync(self, route_id: int, enabled: Optional[bool] = None) -> Dict[str, Any]:
        """
        切换路由状态并同步到 Caddy
        Toggle route status and sync with Caddy
        
        Args:
            route_id: 路由 ID / Route identifier
            enabled: 目标启用状态，None 表示自动取反 / Desired state, None means auto-toggle
            
        Returns:
            结果字典 / Result payload
        """
        logger.info(f"Toggling route {route_id} to {enabled} and syncing")

        try:
            current_route = await self.domain.get_route_details(route_id)
            if not current_route:
                return {
                    "status": "error",
                    "error": "Route not found"
                }

            # 当未指定目标状态时自动翻转当前状态 / Auto flip state when target not provided
            target_state = (not current_route.is_enabled) if enabled is None else enabled

            if target_state == current_route.is_enabled:
                updated_route = current_route
            else:
                updated_route = await self.domain.toggle_route_status(route_id, target_state)
                if not updated_route:
                    return {
                        "status": "error",
                        "error": "Route not found"
                    }

            # 同步到 Caddy，保证与数据库状态一致 / Sync to Caddy to keep it aligned with DB state
            sync_success = await self.domain.sync_routes_to_caddy()

            if not sync_success:
                rollback_success = await self._rollback_update_route(route_id, current_route)
                logger.warning(
                    "Toggle route sync failed, rollback toggle result: %s, route_id=%s",
                    rollback_success,
                    route_id,
                )
                return {
                    "status": "error",
                    "error": "Sync to Caddy failed, toggle rolled back" if rollback_success else (
                        "Sync to Caddy failed, and rollback failed"
                    ),
                    "synced_to_caddy": False,
                    "rollback_success": rollback_success,
                }

            return {
                "status": "success",
                "route": updated_route,
                "synced_to_caddy": sync_success
            }
        except Exception as e:
            logger.error(f"Error toggling route: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def delete_route_and_sync(self, route_id: int) -> Dict[str, Any]:
        """
        删除路由并同步到 Caddy
        
        Args:
            route_id: 路由 ID
            
        Returns:
            结果字典
        """
        logger.info(f"Deleting and syncing route: {route_id}")

        try:
            previous_route = await self.domain.get_route_details(route_id)
            if not previous_route:
                return {
                    "status": "error",
                    "error": "Route not found or deletion failed"
                }

            # 删除路由
            success = await self.domain.remove_route(route_id)

            if not success:
                return {
                    "status": "error",
                    "error": "Route not found or deletion failed"
                }

            # 同步到 Caddy
            sync_success = await self.domain.sync_routes_to_caddy()

            if not sync_success:
                rollback_success = await self._rollback_delete_route(previous_route)
                logger.warning(
                    "Delete route sync failed, rollback delete result: %s, route_id=%s",
                    rollback_success,
                    route_id,
                )
                return {
                    "status": "error",
                    "error": "Sync to Caddy failed, delete rolled back" if rollback_success else (
                        "Sync to Caddy failed, and rollback failed"
                    ),
                    "synced_to_caddy": False,
                    "rollback_success": rollback_success,
                }

            return {
                "status": "success",
                "synced_to_caddy": sync_success
            }
        except Exception as e:
            logger.error(f"Error deleting route: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_route(self, route_id: int) -> Optional[CaddyRoute]:
        """
        获取路由详情
        
        Args:
            route_id: 路由 ID
            
        Returns:
            路由对象或 None
        """
        return await self.domain.get_route_details(route_id)

    async def list_all_routes(self, filters: Optional[Dict[str, Any]] = None) -> List[CaddyRoute]:
        """
        列出所有路由
        
        Args:
            filters: 过滤条件
            
        Returns:
            路由列表
        """
        return await self.domain.list_routes(filters)

    async def list_routes_by_domain(self, domain: str) -> List[CaddyRoute]:
        """
        按域名列出路由
        
        Args:
            domain: 域名
            
        Returns:
            路由列表
        """
        return await self.domain.list_routes_by_domain(domain)

    async def list_routes_by_service(self, service: str) -> List[CaddyRoute]:
        """
        按服务列出路由
        
        Args:
            service: 服务名称
            
        Returns:
            路由列表
        """
        return await self.domain.list_routes_by_service(service)

    async def sync_all_routes(self) -> Dict[str, Any]:
        """
        手动触发同步所有路由到 Caddy
        
        Returns:
            同步结果
        """
        logger.info("Manually syncing all routes to Caddy")

        try:
            success = await self.domain.sync_routes_to_caddy()

            return {
                "status": "success" if success else "error",
                "message": "Routes synced successfully" if success else "Failed to sync routes"
            }
        except Exception as e:
            logger.error(f"Error syncing routes: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_route_statistics(self) -> Dict[str, int]:
        """
        获取路由统计信息
        
        Returns:
            统计信息字典
        """
        total = await self.domain.get_route_count()
        enabled = await self.domain.get_route_count({"is_enabled": True})
        disabled = total - enabled

        return {
            "total": total,
            "enabled": enabled,
            "disabled": disabled
        }

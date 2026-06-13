"""
Caddy 限流规则管理应用服务
协调限流规则管理的业务流程
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import (
    CaddyRateLimit,
    CaddyRateLimitCreate,
    CaddyRateLimitUpdate,
)
from cancan_microstack.services.opsbffsrv.domain.caddy.rate_limit_management import RateLimitManagementDomain
from cancan_microstack.services.opsbffsrv.infrastructure.caddy.admin_api_client import caddy_admin_client


class RateLimitManagementApp:
    """限流规则管理应用服务"""

    def __init__(self):
        self.domain = RateLimitManagementDomain()

    async def _sync_enabled_rules_to_caddy(self) -> bool:
        """同步已启用限流规则到 Caddy
        Sync enabled rate limit rules to Caddy
        """
        enabled_rules = await self.domain.list_rate_limits({"is_enabled": True})
        caddy_rate_limit_routes: List[Dict[str, Any]] = []
        for rule in enabled_rules:
            route_configs = await caddy_admin_client.build_rate_limit_config(rule.model_dump())
            caddy_rate_limit_routes.extend(route_configs)
        return await caddy_admin_client.apply_rate_limits_batch(caddy_rate_limit_routes)

    async def create_rate_limit_rule(self, rate_limit: CaddyRateLimitCreate) -> Dict[str, Any]:
        """
        创建限流规则
        
        Args:
            rate_limit: 限流规则创建对象
            
        Returns:
            结果字典
        """
        logger.info(f"Creating rate limit rule: {rate_limit.rule_name}")

        try:
            created_rule = await self.domain.create_new_rate_limit(rate_limit)

            sync_success = await self._sync_enabled_rules_to_caddy()
            if not sync_success:
                rollback_success = await self.domain.remove_rate_limit(created_rule.id)
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
                "rate_limit": created_rule,
                "synced_to_caddy": True,
            }
        except ValueError as e:
            logger.warning(f"Rate limit creation failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error creating rate limit: {e}", exc_info=True)
            return {
                "status": "error",
                "error": "Internal server error"
            }

    async def update_rate_limit_rule(self, rule_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新限流规则
        
        Args:
            rule_id: 规则 ID
            data: 更新数据
            
        Returns:
            结果字典
        """
        logger.info(f"Updating rate limit rule: {rule_id}")

        try:
            previous_rule = await self.domain.get_rate_limit_details(rule_id)
            if not previous_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found"
                }

            updated_rule = await self.domain.update_existing_rate_limit(rule_id, data)

            if not updated_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found"
                }

            sync_success = await self._sync_enabled_rules_to_caddy()
            if not sync_success:
                rollback_data = previous_rule.model_dump(exclude={"id", "created_time", "update_time"})
                rollback_rule = await self.domain.update_existing_rate_limit(rule_id, rollback_data)
                rollback_success = rollback_rule is not None
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
                "rate_limit": updated_rule,
                "synced_to_caddy": True,
            }
        except ValueError as e:
            logger.warning(f"Rate limit update failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error updating rate limit: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def toggle_rate_limit_rule(self, rule_id: int, enabled: bool) -> Dict[str, Any]:
        """
        切换限流规则状态
        
        Args:
            rule_id: 规则 ID
            enabled: 是否启用
            
        Returns:
            结果字典
        """
        logger.info(f"Toggling rate limit rule {rule_id} to {enabled}")

        try:
            current_rule = await self.domain.get_rate_limit_details(rule_id)
            if not current_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found"
                }

            updated_rule = await self.domain.toggle_rate_limit_status(rule_id, enabled)

            if not updated_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found"
                }

            sync_success = await self._sync_enabled_rules_to_caddy()
            if not sync_success:
                rollback_rule = await self.domain.toggle_rate_limit_status(rule_id, current_rule.is_enabled)
                rollback_success = rollback_rule is not None
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
                "rate_limit": updated_rule,
                "synced_to_caddy": True,
            }
        except Exception as e:
            logger.error(f"Error toggling rate limit: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def delete_rate_limit_rule(self, rule_id: int) -> Dict[str, Any]:
        """
        删除限流规则
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            结果字典
        """
        logger.info(f"Deleting rate limit rule: {rule_id}")

        try:
            existing_rule = await self.domain.get_rate_limit_details(rule_id)
            if not existing_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found or deletion failed"
                }

            success = await self.domain.remove_rate_limit(rule_id)

            if not success:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found or deletion failed"
                }

            sync_success = await self._sync_enabled_rules_to_caddy()
            if not sync_success:
                recreate_payload = CaddyRateLimitCreate.model_validate(
                    existing_rule.model_dump(exclude={"id", "created_time", "update_time"})
                )
                recreated_rule = await self.domain.create_new_rate_limit(recreate_payload)
                rollback_success = recreated_rule is not None
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
                "message": "Rate limit rule deleted successfully",
                "synced_to_caddy": True,
            }
        except Exception as e:
            logger.error(f"Error deleting rate limit: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_rate_limit_rule(self, rule_id: int) -> Optional[CaddyRateLimit]:
        """
        获取限流规则详情
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            限流规则对象或 None
        """
        return await self.domain.get_rate_limit_details(rule_id)

    async def get_rate_limit(self, rule_id: int) -> Optional[CaddyRateLimit]:
        """API 层别名 / API alias for naming consistency."""
        return await self.get_rate_limit_rule(rule_id)

    async def list_all_rate_limits(self, filters: Optional[Dict[str, Any]] = None) -> List[CaddyRateLimit]:
        """
        列出所有限流规则
        
        Args:
            filters: 过滤条件
            
        Returns:
            限流规则列表
        """
        return await self.domain.list_rate_limits(filters)

    async def list_rate_limits(
            self,
            match_type: Optional[str] = None,
            is_enabled: Optional[bool] = None,
    ) -> List[CaddyRateLimit]:
        """API 层别名（带简化过滤参数）/ API alias with simplified filters."""
        filters: Dict[str, Any] = {}
        if match_type is not None:
            filters["match_type"] = match_type
        if is_enabled is not None:
            filters["is_enabled"] = is_enabled
        return await self.list_all_rate_limits(filters=filters if filters else None)

    async def list_rate_limits_by_type(self, match_type: str) -> List[CaddyRateLimit]:
        """
        按匹配类型列出限流规则
        
        Args:
            match_type: 匹配类型
            
        Returns:
            限流规则列表
        """
        return await self.domain.list_rate_limits_by_match_type(match_type)

    async def manage_ip_whitelist(self, rule_id: int, ip: str, action: str) -> Dict[str, Any]:
        """
        管理白名单 IP
        
        Args:
            rule_id: 规则 ID
            ip: IP 地址
            action: 操作（add/remove）
            
        Returns:
            结果字典
        """
        logger.info(f"Managing whitelist IP for rule {rule_id}: {action} {ip}")

        try:
            updated_rule = await self.domain.manage_whitelist_ip(rule_id, ip, action)

            if not updated_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found"
                }

            sync_success = await self._sync_enabled_rules_to_caddy()
            if not sync_success:
                rollback_action = "remove" if action == "add" else "add"
                rollback_rule = await self.domain.manage_whitelist_ip(rule_id, ip, rollback_action)
                rollback_success = rollback_rule is not None
                return {
                    "status": "error",
                    "error": "Sync to Caddy failed, whitelist change rolled back" if rollback_success else (
                        "Sync to Caddy failed, and rollback failed"
                    ),
                    "synced_to_caddy": False,
                    "rollback_success": rollback_success,
                }

            return {
                "status": "success",
                "rate_limit": updated_rule,
                "synced_to_caddy": True,
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error managing whitelist IP: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def manage_ip_blacklist(self, rule_id: int, ip: str, action: str) -> Dict[str, Any]:
        """
        管理黑名单 IP
        
        Args:
            rule_id: 规则 ID
            ip: IP 地址
            action: 操作（add/remove）
            
        Returns:
            结果字典
        """
        logger.info(f"Managing blacklist IP for rule {rule_id}: {action} {ip}")

        try:
            updated_rule = await self.domain.manage_blacklist_ip(rule_id, ip, action)

            if not updated_rule:
                return {
                    "status": "error",
                    "error": "Rate limit rule not found"
                }

            sync_success = await self._sync_enabled_rules_to_caddy()
            if not sync_success:
                rollback_action = "remove" if action == "add" else "add"
                rollback_rule = await self.domain.manage_blacklist_ip(rule_id, ip, rollback_action)
                rollback_success = rollback_rule is not None
                return {
                    "status": "error",
                    "error": "Sync to Caddy failed, blacklist change rolled back" if rollback_success else (
                        "Sync to Caddy failed, and rollback failed"
                    ),
                    "synced_to_caddy": False,
                    "rollback_success": rollback_success,
                }

            return {
                "status": "success",
                "rate_limit": updated_rule,
                "synced_to_caddy": True,
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error managing blacklist IP: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_rate_limit_statistics(self) -> Dict[str, int]:
        """
        获取限流规则统计信息
        
        Returns:
            统计信息字典
        """
        total = await self.domain.get_rate_limit_count()
        enabled = await self.domain.get_rate_limit_count({"is_enabled": True})
        disabled = total - enabled

        return {
            "total": total,
            "enabled": enabled,
            "disabled": disabled
        }

    async def create_rate_limit(self, rule_data: CaddyRateLimitCreate) -> Dict[str, Any]:
        """API 层别名 / API alias."""
        return await self.create_rate_limit_rule(rule_data)

    async def update_rate_limit(self, rule_id: int, rule_data: CaddyRateLimitUpdate) -> Dict[str, Any]:
        """API 层别名 / API alias."""
        return await self.update_rate_limit_rule(rule_id, rule_data.model_dump(exclude_unset=True))

    async def delete_rate_limit(self, rule_id: int) -> Dict[str, Any]:
        """API 层别名 / API alias."""
        return await self.delete_rate_limit_rule(rule_id)

    async def toggle_rate_limit(self, rule_id: int) -> Dict[str, Any]:
        """API 层别名（自动反转状态）/ API alias with automatic status inversion."""
        current_rule = await self.domain.get_rate_limit_details(rule_id)
        if not current_rule:
            return {
                "status": "error",
                "error": "Rate limit rule not found"
            }
        return await self.toggle_rate_limit_rule(rule_id, not current_rule.is_enabled)

    async def add_whitelist_ips(self, rule_id: int, ips: List[str]) -> Dict[str, Any]:
        """批量添加白名单 IP
        Add whitelist IPs in batch
        """
        last_result: Dict[str, Any] = {"status": "success"}
        for ip in ips:
            last_result = await self.manage_ip_whitelist(rule_id, ip, "add")
            if last_result.get("status") != "success":
                return last_result
        return last_result

    async def remove_whitelist_ips(self, rule_id: int, ips: List[str]) -> Dict[str, Any]:
        """批量移除白名单 IP
        Remove whitelist IPs in batch
        """
        last_result: Dict[str, Any] = {"status": "success"}
        for ip in ips:
            last_result = await self.manage_ip_whitelist(rule_id, ip, "remove")
            if last_result.get("status") != "success":
                return last_result
        return last_result

    async def add_blacklist_ips(self, rule_id: int, ips: List[str]) -> Dict[str, Any]:
        """批量添加黑名单 IP
        Add blacklist IPs in batch
        """
        last_result: Dict[str, Any] = {"status": "success"}
        for ip in ips:
            last_result = await self.manage_ip_blacklist(rule_id, ip, "add")
            if last_result.get("status") != "success":
                return last_result
        return last_result

    async def remove_blacklist_ips(self, rule_id: int, ips: List[str]) -> Dict[str, Any]:
        """批量移除黑名单 IP
        Remove blacklist IPs in batch
        """
        last_result: Dict[str, Any] = {"status": "success"}
        for ip in ips:
            last_result = await self.manage_ip_blacklist(rule_id, ip, "remove")
            if last_result.get("status") != "success":
                return last_result
        return last_result

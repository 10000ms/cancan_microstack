"""
Caddy 限流规则管理领域服务
包含限流规则的核心业务逻辑和业务规则
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyRateLimit, CaddyRateLimitCreate
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_rate_limit import (
    get_rate_limit_by_id,
    get_rate_limit_by_name,
    get_enabled_rate_limits,
    get_rate_limits_by_match_type,
    get_all_rate_limits,
    create_rate_limit,
    update_rate_limit,
    update_rate_limit_by_name,
    enable_rate_limit,
    disable_rate_limit,
    delete_rate_limit,
    delete_rate_limit_by_name,
    add_whitelist_ip,
    remove_whitelist_ip,
    add_blacklist_ip,
    remove_blacklist_ip,
    count_rate_limits,
)


class RateLimitManagementDomain:
    """限流规则管理领域服务"""

    async def create_new_rate_limit(self, rate_limit: CaddyRateLimitCreate) -> CaddyRateLimit:
        """
        创建新限流规则
        
        业务规则：
        1. 规则名称必须唯一
        2. 限流值必须大于 0
        3. 时间窗口至少 1 秒
        4. 优先级范围：0-1000
        
        Args:
            rate_limit: 限流规则创建对象
            
        Returns:
            创建后的限流规则对象
            
        Raises:
            ValueError: 业务规则违反
        """
        logger.info(f"Creating new rate limit rule: {rate_limit.rule_name}")

        # 业务规则验证
        await self._validate_rate_limit_create(rate_limit)

        # 创建数据库记录
        db_rate_limit = await create_rate_limit(rate_limit)
        logger.info(f"Rate limit rule created in database: {db_rate_limit.id}")

        return db_rate_limit

    async def update_existing_rate_limit(self, rule_id: int, data: Dict[str, Any]) -> Optional[CaddyRateLimit]:
        """
        更新现有限流规则
        
        Args:
            rule_id: 规则 ID
            data: 更新数据
            
        Returns:
            更新后的限流规则对象或 None
        """
        logger.info(f"Updating rate limit rule: {rule_id}")

        # 验证规则存在
        existing_rule = await get_rate_limit_by_id(rule_id)
        if not existing_rule:
            logger.warning(f"Rate limit rule not found: {rule_id}")
            return None

        # 验证更新数据
        if 'limit_value' in data and data['limit_value'] <= 0:
            raise ValueError("Limit value must be greater than 0")

        if 'limit_window' in data and data['limit_window'] < 1:
            raise ValueError("Limit window must be at least 1 second")

        # 更新数据库记录
        updated_rule = await update_rate_limit(rule_id, data)

        if updated_rule:
            logger.info(f"Rate limit rule updated: {rule_id}")

        return updated_rule

    async def toggle_rate_limit_status(self, rule_id: int, enabled: bool) -> Optional[CaddyRateLimit]:
        """
        切换限流规则启用状态
        
        Args:
            rule_id: 规则 ID
            enabled: 是否启用
            
        Returns:
            更新后的限流规则对象或 None
        """
        logger.info(f"Toggling rate limit rule {rule_id} status to: {enabled}")

        if enabled:
            updated_rule = await enable_rate_limit(rule_id)
        else:
            updated_rule = await disable_rate_limit(rule_id)

        return updated_rule

    async def remove_rate_limit(self, rule_id: int) -> bool:
        """
        删除限流规则
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            是否删除成功
        """
        logger.info(f"Removing rate limit rule: {rule_id}")

        # 验证规则存在
        existing_rule = await get_rate_limit_by_id(rule_id)
        if not existing_rule:
            logger.warning(f"Rate limit rule not found: {rule_id}")
            return False

        # 删除数据库记录
        success = await delete_rate_limit(rule_id)

        if success:
            logger.info(f"Rate limit rule removed: {rule_id}")

        return success

    async def get_rate_limit_details(self, rule_id: int) -> Optional[CaddyRateLimit]:
        """
        获取限流规则详情
        
        Args:
            rule_id: 规则 ID
            
        Returns:
            限流规则对象或 None
        """
        return await get_rate_limit_by_id(rule_id)

    async def list_rate_limits(self, filters: Optional[Dict[str, Any]] = None) -> List[CaddyRateLimit]:
        """
        列出限流规则
        
        Args:
            filters: 过滤条件
            
        Returns:
            限流规则列表
        """
        return await get_all_rate_limits(filters)

    async def list_rate_limits_by_match_type(self, match_type: str) -> List[CaddyRateLimit]:
        """
        按匹配类型列出限流规则
        
        Args:
            match_type: 匹配类型（path/domain/ip/header/all）
            
        Returns:
            限流规则列表
        """
        return await get_rate_limits_by_match_type(match_type)

    async def manage_whitelist_ip(self, rule_id: int, ip: str, action: str) -> Optional[CaddyRateLimit]:
        """
        管理白名单 IP
        
        Args:
            rule_id: 规则 ID
            ip: IP 地址
            action: 操作（add/remove）
            
        Returns:
            更新后的限流规则对象或 None
            
        Raises:
            ValueError: 操作无效
        """
        logger.info(f"Managing whitelist IP for rule {rule_id}: {action} {ip}")

        # 验证 IP 格式
        if not self._is_valid_ip(ip):
            raise ValueError(f"Invalid IP address: {ip}")

        if action == "add":
            return await add_whitelist_ip(rule_id, ip)
        elif action == "remove":
            return await remove_whitelist_ip(rule_id, ip)
        else:
            raise ValueError(f"Invalid action: {action}. Must be 'add' or 'remove'")

    async def manage_blacklist_ip(self, rule_id: int, ip: str, action: str) -> Optional[CaddyRateLimit]:
        """
        管理黑名单 IP
        
        Args:
            rule_id: 规则 ID
            ip: IP 地址
            action: 操作（add/remove）
            
        Returns:
            更新后的限流规则对象或 None
            
        Raises:
            ValueError: 操作无效
        """
        logger.info(f"Managing blacklist IP for rule {rule_id}: {action} {ip}")

        # 验证 IP 格式
        if not self._is_valid_ip(ip):
            raise ValueError(f"Invalid IP address: {ip}")

        if action == "add":
            return await add_blacklist_ip(rule_id, ip)
        elif action == "remove":
            return await remove_blacklist_ip(rule_id, ip)
        else:
            raise ValueError(f"Invalid action: {action}. Must be 'add' or 'remove'")

    async def get_rate_limit_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        获取限流规则数量
        
        Args:
            filters: 过滤条件
            
        Returns:
            规则数量
        """
        return await count_rate_limits(filters)

    async def _validate_rate_limit_create(self, rate_limit: CaddyRateLimitCreate):
        """
        验证限流规则创建的业务规则
        
        Args:
            rate_limit: 限流规则创建对象
            
        Raises:
            ValueError: 业务规则违反
        """
        # 验证规则名称唯一性
        existing_rule = await get_rate_limit_by_name(rate_limit.rule_name)
        if existing_rule:
            raise ValueError(f"Rate limit rule name already exists: {rate_limit.rule_name}")

        # 验证限流值
        if rate_limit.limit_value <= 0:
            raise ValueError("Limit value must be greater than 0")

        # 验证时间窗口
        if rate_limit.limit_window < 1:
            raise ValueError("Limit window must be at least 1 second")

        # 验证优先级范围
        if rate_limit.priority < 0 or rate_limit.priority > 1000:
            raise ValueError(f"Priority must be between 0 and 1000: {rate_limit.priority}")

        # 验证匹配类型
        valid_match_types = ['path', 'domain', 'ip', 'header', 'all']
        if rate_limit.match_type not in valid_match_types:
            raise ValueError(f"Invalid match type: {rate_limit.match_type}. Must be one of {valid_match_types}")

        # 验证限流类型
        valid_limit_types = ['request', 'bandwidth']
        if rate_limit.limit_type not in valid_limit_types:
            raise ValueError(f"Invalid limit type: {rate_limit.limit_type}. Must be one of {valid_limit_types}")

        # 验证限流键
        valid_limit_keys = ['ip', 'header', 'cookie', 'path']
        if rate_limit.limit_key not in valid_limit_keys:
            raise ValueError(f"Invalid limit key: {rate_limit.limit_key}. Must be one of {valid_limit_keys}")

    def _is_valid_ip(self, ip: str) -> bool:
        """
        验证 IP 地址格式
        
        Args:
            ip: IP 地址字符串
            
        Returns:
            是否为有效 IP
        """
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

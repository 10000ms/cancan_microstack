"""
Caddy 限流规则表的数据库操作函数
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.caddy import CaddyRateLimit, CaddyRateLimitCreate
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.caddy_rate_limit_tbl import CaddyRateLimitTbl


async def get_rate_limit_by_id(rule_id: int) -> Optional[CaddyRateLimit]:
    """
    根据 ID 查询限流规则
    
    Args:
        rule_id: 规则 ID
        
    Returns:
        限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRateLimitTbl).where(CaddyRateLimitTbl.id == rule_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRateLimit.model_validate(row, from_attributes=True) if row else None


async def get_rate_limit_by_name(rule_name: str) -> Optional[CaddyRateLimit]:
    """
    根据规则名称查询限流规则
    
    Args:
        rule_name: 规则名称
        
    Returns:
        限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRateLimitTbl).where(CaddyRateLimitTbl.rule_name == rule_name)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRateLimit.model_validate(row, from_attributes=True) if row else None


async def get_enabled_rate_limits() -> List[CaddyRateLimit]:
    """
    查询所有已启用的限流规则
    
    Returns:
        限流规则列表（按优先级降序）
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRateLimitTbl).where(
                CaddyRateLimitTbl.is_enabled == True
            ).order_by(CaddyRateLimitTbl.priority.desc(), CaddyRateLimitTbl.created_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRateLimit.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_rate_limits_by_match_type(match_type: str) -> List[CaddyRateLimit]:
    """
    根据匹配类型查询限流规则
    
    Args:
        match_type: 匹配类型（path/domain/ip/header/all）
        
    Returns:
        限流规则列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRateLimitTbl).where(
                CaddyRateLimitTbl.match_type == match_type
            ).order_by(CaddyRateLimitTbl.priority.desc())
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRateLimit.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_all_rate_limits(filters: Optional[Dict[str, Any]] = None) -> List[CaddyRateLimit]:
    """
    查询所有限流规则（支持动态过滤）
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        限流规则列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRateLimitTbl)

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyRateLimitTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyRateLimitTbl, key) == value)

            stmt = stmt.order_by(CaddyRateLimitTbl.priority.desc(), CaddyRateLimitTbl.created_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRateLimit.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def create_rate_limit(rate_limit: CaddyRateLimitCreate) -> CaddyRateLimit:
    """
    创建新限流规则
    
    Args:
        rate_limit: 限流规则创建对象
        
    Returns:
        创建后的限流规则对象
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(CaddyRateLimitTbl).values(
                **rate_limit.model_dump()
            ).returning(CaddyRateLimitTbl)
            row = (await session.execute(stmt)).scalar_one()
            return CaddyRateLimit.model_validate(row, from_attributes=True)


async def update_rate_limit(rule_id: int, data: Dict[str, Any]) -> Optional[CaddyRateLimit]:
    """
    更新限流规则
    
    Args:
        rule_id: 规则 ID
        data: 更新数据字典
        
    Returns:
        更新后的限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(CaddyRateLimitTbl).where(
                CaddyRateLimitTbl.id == rule_id
            ).values(**data).returning(CaddyRateLimitTbl)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRateLimit.model_validate(row, from_attributes=True) if row else None


async def update_rate_limit_by_name(rule_name: str, data: Dict[str, Any]) -> Optional[CaddyRateLimit]:
    """
    根据规则名称更新限流规则
    
    Args:
        rule_name: 规则名称
        data: 更新数据字典
        
    Returns:
        更新后的限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(CaddyRateLimitTbl).where(
                CaddyRateLimitTbl.rule_name == rule_name
            ).values(**data).returning(CaddyRateLimitTbl)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRateLimit.model_validate(row, from_attributes=True) if row else None


async def enable_rate_limit(rule_id: int) -> Optional[CaddyRateLimit]:
    """
    启用限流规则
    
    Args:
        rule_id: 规则 ID
        
    Returns:
        更新后的限流规则对象或 None
    """
    return await update_rate_limit(rule_id, {"is_enabled": True})


async def disable_rate_limit(rule_id: int) -> Optional[CaddyRateLimit]:
    """
    禁用限流规则
    
    Args:
        rule_id: 规则 ID
        
    Returns:
        更新后的限流规则对象或 None
    """
    return await update_rate_limit(rule_id, {"is_enabled": False})


async def delete_rate_limit(rule_id: int) -> bool:
    """
    删除限流规则
    
    Args:
        rule_id: 规则 ID
        
    Returns:
        是否删除成功
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyRateLimitTbl).where(CaddyRateLimitTbl.id == rule_id)
            result = await session.execute(stmt)
            return result.rowcount > 0


async def delete_rate_limit_by_name(rule_name: str) -> bool:
    """
    根据规则名称删除限流规则
    
    Args:
        rule_name: 规则名称
        
    Returns:
        是否删除成功
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyRateLimitTbl).where(CaddyRateLimitTbl.rule_name == rule_name)
            result = await session.execute(stmt)
            return result.rowcount > 0


async def add_whitelist_ip(rule_id: int, ip: str) -> Optional[CaddyRateLimit]:
    """
    添加 IP 到白名单
    
    Args:
        rule_id: 规则 ID
        ip: IP 地址
        
    Returns:
        更新后的限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 查询当前规则
            stmt = select(CaddyRateLimitTbl).where(CaddyRateLimitTbl.id == rule_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if not row:
                return None

            # 添加到白名单
            whitelist = list(row.whitelist_ips) if row.whitelist_ips else []
            if ip not in whitelist:
                whitelist.append(ip)
                return await update_rate_limit(rule_id, {"whitelist_ips": whitelist})
            return CaddyRateLimit.model_validate(row, from_attributes=True)


async def remove_whitelist_ip(rule_id: int, ip: str) -> Optional[CaddyRateLimit]:
    """
    从白名单移除 IP
    
    Args:
        rule_id: 规则 ID
        ip: IP 地址
        
    Returns:
        更新后的限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 查询当前规则
            stmt = select(CaddyRateLimitTbl).where(CaddyRateLimitTbl.id == rule_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if not row:
                return None

            # 从白名单移除
            whitelist = list(row.whitelist_ips) if row.whitelist_ips else []
            if ip in whitelist:
                whitelist.remove(ip)
                return await update_rate_limit(rule_id, {"whitelist_ips": whitelist})
            return CaddyRateLimit.model_validate(row, from_attributes=True)


async def add_blacklist_ip(rule_id: int, ip: str) -> Optional[CaddyRateLimit]:
    """
    添加 IP 到黑名单
    
    Args:
        rule_id: 规则 ID
        ip: IP 地址
        
    Returns:
        更新后的限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 查询当前规则
            stmt = select(CaddyRateLimitTbl).where(CaddyRateLimitTbl.id == rule_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if not row:
                return None

            # 添加到黑名单
            blacklist = list(row.blacklist_ips) if row.blacklist_ips else []
            if ip not in blacklist:
                blacklist.append(ip)
                return await update_rate_limit(rule_id, {"blacklist_ips": blacklist})
            return CaddyRateLimit.model_validate(row, from_attributes=True)


async def remove_blacklist_ip(rule_id: int, ip: str) -> Optional[CaddyRateLimit]:
    """
    从黑名单移除 IP
    
    Args:
        rule_id: 规则 ID
        ip: IP 地址
        
    Returns:
        更新后的限流规则对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 查询当前规则
            stmt = select(CaddyRateLimitTbl).where(CaddyRateLimitTbl.id == rule_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if not row:
                return None

            # 从黑名单移除
            blacklist = list(row.blacklist_ips) if row.blacklist_ips else []
            if ip in blacklist:
                blacklist.remove(ip)
                return await update_rate_limit(rule_id, {"blacklist_ips": blacklist})
            return CaddyRateLimit.model_validate(row, from_attributes=True)


async def count_rate_limits(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    统计限流规则数量
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        规则数量
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(func.count(CaddyRateLimitTbl.id))

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyRateLimitTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyRateLimitTbl, key) == value)

            count = (await session.execute(stmt)).scalar_one()
            return count

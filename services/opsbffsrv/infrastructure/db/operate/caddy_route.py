"""
Caddy 路由表的数据库操作函数
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
from cancan_microstack.public.schemas.caddy import CaddyRoute, CaddyRouteCreate
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.caddy_route_tbl import CaddyRouteTbl


async def get_route_by_id(route_id: int) -> Optional[CaddyRoute]:
    """
    根据 ID 查询单条路由记录
    
    Args:
        route_id: 路由 ID
        
    Returns:
        路由对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRouteTbl).where(CaddyRouteTbl.id == route_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRoute.model_validate(row, from_attributes=True) if row else None


async def get_route_by_name(route_name: str) -> Optional[CaddyRoute]:
    """
    根据路由名称查询记录
    
    Args:
        route_name: 路由名称
        
    Returns:
        路由对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRouteTbl).where(CaddyRouteTbl.route_name == route_name)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRoute.model_validate(row, from_attributes=True) if row else None


async def get_routes_by_domain(domain: str) -> List[CaddyRoute]:
    """
    根据域名查询路由列表
    
    Args:
        domain: 域名
        
    Returns:
        路由对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRouteTbl).where(
                CaddyRouteTbl.domain == domain
            ).order_by(CaddyRouteTbl.priority.desc())
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRoute.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_routes_by_service(upstream_service: str) -> List[CaddyRoute]:
    """
    根据上游服务查询路由列表
    
    Args:
        upstream_service: 上游服务名称
        
    Returns:
        路由对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRouteTbl).where(
                CaddyRouteTbl.upstream_service == upstream_service
            ).order_by(CaddyRouteTbl.priority.desc())
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRoute.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_enabled_routes() -> List[CaddyRoute]:
    """
    查询所有已启用的路由
    
    Returns:
        路由对象列表（按优先级降序）
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRouteTbl).where(
                CaddyRouteTbl.is_enabled == True
            ).order_by(CaddyRouteTbl.priority.desc(), CaddyRouteTbl.created_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRoute.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_all_routes(filters: Optional[Dict[str, Any]] = None) -> List[CaddyRoute]:
    """
    查询所有路由（支持动态过滤）
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        路由对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyRouteTbl)

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyRouteTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyRouteTbl, key) == value)

            stmt = stmt.order_by(CaddyRouteTbl.priority.desc(), CaddyRouteTbl.created_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyRoute.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def create_route(route: CaddyRouteCreate) -> CaddyRoute:
    """
    创建新路由
    
    Args:
        route: 路由创建对象
        
    Returns:
        创建后的路由对象
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(CaddyRouteTbl).values(
                **route.model_dump()
            ).returning(CaddyRouteTbl)
            row = (await session.execute(stmt)).scalar_one()
            return CaddyRoute.model_validate(row, from_attributes=True)


async def update_route(route_id: int, data: Dict[str, Any]) -> Optional[CaddyRoute]:
    """
    更新路由
    
    Args:
        route_id: 路由 ID
        data: 更新数据字典
        
    Returns:
        更新后的路由对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(CaddyRouteTbl).where(
                CaddyRouteTbl.id == route_id
            ).values(**data).returning(CaddyRouteTbl)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRoute.model_validate(row, from_attributes=True) if row else None


async def update_route_by_name(route_name: str, data: Dict[str, Any]) -> Optional[CaddyRoute]:
    """
    根据路由名称更新路由
    
    Args:
        route_name: 路由名称
        data: 更新数据字典
        
    Returns:
        更新后的路由对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(CaddyRouteTbl).where(
                CaddyRouteTbl.route_name == route_name
            ).values(**data).returning(CaddyRouteTbl)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyRoute.model_validate(row, from_attributes=True) if row else None


async def enable_route(route_id: int) -> Optional[CaddyRoute]:
    """
    启用路由
    
    Args:
        route_id: 路由 ID
        
    Returns:
        更新后的路由对象或 None
    """
    return await update_route(route_id, {"is_enabled": True})


async def disable_route(route_id: int) -> Optional[CaddyRoute]:
    """
    禁用路由
    
    Args:
        route_id: 路由 ID
        
    Returns:
        更新后的路由对象或 None
    """
    return await update_route(route_id, {"is_enabled": False})


async def delete_route(route_id: int) -> bool:
    """
    删除路由
    
    Args:
        route_id: 路由 ID
        
    Returns:
        是否删除成功
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyRouteTbl).where(CaddyRouteTbl.id == route_id)
            result = await session.execute(stmt)
            return result.rowcount > 0


async def delete_route_by_name(route_name: str) -> bool:
    """
    根据路由名称删除路由
    
    Args:
        route_name: 路由名称
        
    Returns:
        是否删除成功
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyRouteTbl).where(CaddyRouteTbl.route_name == route_name)
            result = await session.execute(stmt)
            return result.rowcount > 0


async def count_routes(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    统计路由数量
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        路由数量
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(func.count(CaddyRouteTbl.id))

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyRouteTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyRouteTbl, key) == value)

            count = (await session.execute(stmt)).scalar_one()
            return count

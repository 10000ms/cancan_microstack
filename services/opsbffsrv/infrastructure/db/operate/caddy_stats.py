"""
Caddy 统计数据表的数据库操作函数
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import datetime
from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.caddy import CaddyStats, StatsQuery
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.caddy_stats_tbl import CaddyStatsTbl


async def create_stats(stats: CaddyStats) -> CaddyStats:
    """
    创建统计记录
    
    Args:
        stats: 统计对象
        
    Returns:
        创建后的统计对象
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(CaddyStatsTbl).values(
                **stats.model_dump(exclude={'id', 'created_time', 'update_time'})
            ).returning(CaddyStatsTbl)
            row = (await session.execute(stmt)).scalar_one()
            return CaddyStats.model_validate(row, from_attributes=True)


async def upsert_stats(stats: CaddyStats) -> CaddyStats:
    """
    插入或更新统计记录（基于唯一约束）
    
    Args:
        stats: 统计对象
        
    Returns:
        创建/更新后的统计对象
    """
    from sqlalchemy import select, update, and_, or_

    async with Rmanager.pg_session() as session:
        async with session.begin():
            values = stats.model_dump(exclude={'id', 'created_time', 'update_time'})

            # 处理 dimension_value 为 None 的情况（匹配唯一索引逻辑）
            dimension_value = values.get('dimension_value') or ''

            # 先尝试查找现有记录
            stmt = select(CaddyStatsTbl).where(
                and_(
                    CaddyStatsTbl.stat_time == values['stat_time'],
                    CaddyStatsTbl.stat_period == values['stat_period'],
                    CaddyStatsTbl.dimension_type == values['dimension_type'],
                    or_(
                        CaddyStatsTbl.dimension_value == dimension_value,
                        and_(
                            CaddyStatsTbl.dimension_value.is_(None),
                            dimension_value == ''
                        )
                    )
                )
            )
            existing_row = (await session.execute(stmt)).scalar_one_or_none()

            if existing_row:
                # 更新现有记录
                update_values = {k: v for k, v in values.items()
                                 if k not in ['stat_time', 'stat_period', 'dimension_type', 'dimension_value']}
                stmt = update(CaddyStatsTbl).where(
                    CaddyStatsTbl.id == existing_row.id
                ).values(**update_values).returning(CaddyStatsTbl)
                row = (await session.execute(stmt)).scalar_one()
            else:
                # 插入新记录
                if values.get('dimension_value') is None:
                    values['dimension_value'] = ''
                stmt = insert(CaddyStatsTbl).values(**values).returning(CaddyStatsTbl)
                row = (await session.execute(stmt)).scalar_one()

            return CaddyStats.model_validate(row, from_attributes=True)


async def get_stats_by_id(stats_id: int) -> Optional[CaddyStats]:
    """
    根据 ID 查询统计记录
    
    Args:
        stats_id: 统计记录 ID
        
    Returns:
        统计对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(CaddyStatsTbl.id == stats_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyStats.model_validate(row, from_attributes=True) if row else None


async def query_stats(query: StatsQuery) -> List[CaddyStats]:
    """
    根据查询条件查询统计数据
    
    Args:
        query: 查询参数对象
        
    Returns:
        统计数据列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl)

            # 构建查询条件
            conditions = []

            if query.stat_period:
                conditions.append(CaddyStatsTbl.stat_period == query.stat_period)

            if query.dimension_type:
                conditions.append(CaddyStatsTbl.dimension_type == query.dimension_type)

            if query.dimension_value:
                conditions.append(CaddyStatsTbl.dimension_value == query.dimension_value)

            if query.start_time:
                conditions.append(CaddyStatsTbl.stat_time >= query.start_time)

            if query.end_time:
                conditions.append(CaddyStatsTbl.stat_time <= query.end_time)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            # 排序和分页
            stmt = stmt.order_by(desc(CaddyStatsTbl.stat_time))
            stmt = stmt.limit(query.limit)

            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyStats.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_global_stats(stat_period: str, start_time: datetime, end_time: datetime) -> List[CaddyStats]:
    """
    查询全局统计数据
    
    Args:
        stat_period: 统计周期（minute/hour/day/month）
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        统计数据列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(
                and_(
                    CaddyStatsTbl.stat_period == stat_period,
                    CaddyStatsTbl.dimension_type == 'global',
                    CaddyStatsTbl.stat_time >= start_time,
                    CaddyStatsTbl.stat_time <= end_time
                )
            ).order_by(CaddyStatsTbl.stat_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyStats.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_service_stats(upstream_service: str, stat_period: str, start_time: datetime, end_time: datetime) -> List[
    CaddyStats]:
    """
    查询服务级别统计数据
    
    Args:
        upstream_service: 上游服务名称
        stat_period: 统计周期
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        统计数据列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(
                and_(
                    CaddyStatsTbl.stat_period == stat_period,
                    CaddyStatsTbl.dimension_type == 'service',
                    CaddyStatsTbl.dimension_value == upstream_service,
                    CaddyStatsTbl.stat_time >= start_time,
                    CaddyStatsTbl.stat_time <= end_time
                )
            ).order_by(CaddyStatsTbl.stat_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyStats.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_route_stats(route_name: str, stat_period: str, start_time: datetime, end_time: datetime) -> List[
    CaddyStats]:
    """
    查询路由级别统计数据
    
    Args:
        route_name: 路由名称
        stat_period: 统计周期
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        统计数据列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(
                and_(
                    CaddyStatsTbl.stat_period == stat_period,
                    CaddyStatsTbl.dimension_type == 'route',
                    CaddyStatsTbl.dimension_value == route_name,
                    CaddyStatsTbl.stat_time >= start_time,
                    CaddyStatsTbl.stat_time <= end_time
                )
            ).order_by(CaddyStatsTbl.stat_time)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyStats.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_country_stats(stat_period: str, limit: int = 20) -> List[CaddyStats]:
    """
    查询国家级别统计数据（Top N）
    
    Args:
        stat_period: 统计周期
        limit: 返回数量限制
        
    Returns:
        统计数据列表（按请求数降序）
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(
                and_(
                    CaddyStatsTbl.stat_period == stat_period,
                    CaddyStatsTbl.dimension_type == 'country'
                )
            ).order_by(desc(CaddyStatsTbl.total_requests)).limit(limit)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyStats.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_ip_stats(stat_period: str, limit: int = 20) -> List[CaddyStats]:
    """
    查询 IP 级别统计数据（Top N）
    
    Args:
        stat_period: 统计周期
        limit: 返回数量限制
        
    Returns:
        统计数据列表（按请求数降序）
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(
                and_(
                    CaddyStatsTbl.stat_period == stat_period,
                    CaddyStatsTbl.dimension_type == 'ip'
                )
            ).order_by(desc(CaddyStatsTbl.total_requests)).limit(limit)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyStats.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_latest_stats(dimension_type: str, dimension_value: Optional[str] = None) -> Optional[CaddyStats]:
    """
    获取最新的统计数据
    
    Args:
        dimension_type: 维度类型
        dimension_value: 维度值
        
    Returns:
        最新的统计对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyStatsTbl).where(CaddyStatsTbl.dimension_type == dimension_type)

            if dimension_value:
                stmt = stmt.where(CaddyStatsTbl.dimension_value == dimension_value)

            stmt = stmt.order_by(desc(CaddyStatsTbl.stat_time)).limit(1)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyStats.model_validate(row, from_attributes=True) if row else None


async def delete_old_stats(before_time: datetime) -> int:
    """
    删除指定时间之前的统计数据
    
    Args:
        before_time: 删除此时间之前的统计数据
        
    Returns:
        删除的记录数
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyStatsTbl).where(CaddyStatsTbl.stat_time < before_time)
            result = await session.execute(stmt)
            return result.rowcount


async def count_stats(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    统计记录数量
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        统计记录数量
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(func.count(CaddyStatsTbl.id))

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyStatsTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyStatsTbl, key) == value)

            count = (await session.execute(stmt)).scalar_one()
            return count

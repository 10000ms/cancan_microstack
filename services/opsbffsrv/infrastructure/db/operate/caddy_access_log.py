"""
Caddy 访问日志表的数据库操作函数
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import datetime
from sqlalchemy import (
    and_,
    case,
    delete,
    desc,
    func,
    not_,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager

from cancan_microstack.public.const.caddy_consts import InternalRequestPath
from cancan_microstack.public.schemas.caddy import (
    CaddyAccessLog,
    AccessLogQuery,
)
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.caddy_access_log_tbl import CaddyAccessLogTbl


def _build_non_internal_traffic_condition():
    """构建统一的“非内部系统请求”过滤条件
    Build unified filter to exclude internal system traffic from metrics
    """
    return not_(
        or_(
            CaddyAccessLogTbl.path == InternalRequestPath.HEALTH_CHECK.value,
            CaddyAccessLogTbl.path.like(InternalRequestPath.INTERNAL_SQL_LIKE.value),
            CaddyAccessLogTbl.path.like(InternalRequestPath.OPSBFF_API_SQL_LIKE.value),
        )
    )


async def create_access_log(log: CaddyAccessLog) -> CaddyAccessLog:
    """
    创建访问日志记录
    
    Args:
        log: 访问日志对象
        
    Returns:
        创建后的访问日志对象
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(CaddyAccessLogTbl).values(
                **log.model_dump(exclude={'id', 'created_time'})
            ).returning(CaddyAccessLogTbl)
            row = (await session.execute(stmt)).scalar_one()
            return CaddyAccessLog.model_validate(row, from_attributes=True)


async def batch_create_access_logs(logs: List[CaddyAccessLog]) -> None:
    """
    批量创建访问日志记录
    
    Args:
        logs: 访问日志对象列表
    """
    import itertools

    async with Rmanager.pg_session() as session:
        # 分批插入，每批 500 条
        batched_iter = itertools.batched(logs, 500)
        for chunk in batched_iter:
            async with session.begin():
                stmt = insert(CaddyAccessLogTbl).values([
                    log.model_dump(exclude={'id', 'created_time'}) for log in chunk
                ])
                await session.execute(stmt)


async def get_access_log_by_id(log_id: int) -> Optional[CaddyAccessLog]:
    """
    根据 ID 查询访问日志
    
    Args:
        log_id: 日志 ID
        
    Returns:
        访问日志对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl).where(CaddyAccessLogTbl.id == log_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyAccessLog.model_validate(row, from_attributes=True) if row else None


async def get_access_log_by_request_id(request_id: str) -> Optional[CaddyAccessLog]:
    """
    根据请求 ID 查询访问日志
    
    Args:
        request_id: 请求 ID
        
    Returns:
        访问日志对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl).where(CaddyAccessLogTbl.request_id == request_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyAccessLog.model_validate(row, from_attributes=True) if row else None


async def query_access_logs(query: AccessLogQuery) -> List[CaddyAccessLog]:
    """
    根据查询条件查询访问日志
    
    Args:
        query: 查询参数对象
        
    Returns:
        访问日志列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl)

            # 构建查询条件
            conditions = []

            if query.client_ip:
                conditions.append(CaddyAccessLogTbl.client_ip == query.client_ip)

            if query.country:
                conditions.append(CaddyAccessLogTbl.country == query.country)

            if query.country_code:
                conditions.append(CaddyAccessLogTbl.country_code == query.country_code)

            if query.upstream_service:
                conditions.append(CaddyAccessLogTbl.upstream_service == query.upstream_service)

            if query.matched_route:
                conditions.append(CaddyAccessLogTbl.matched_route == query.matched_route)

            if query.waf_action:
                conditions.append(CaddyAccessLogTbl.waf_action == query.waf_action)

            if query.rate_limited is not None:
                conditions.append(CaddyAccessLogTbl.rate_limited == query.rate_limited)

            if query.min_response_time is not None:
                conditions.append(CaddyAccessLogTbl.response_time >= query.min_response_time)

            if query.max_response_time is not None:
                conditions.append(CaddyAccessLogTbl.response_time <= query.max_response_time)

            if query.start_time:
                conditions.append(CaddyAccessLogTbl.timestamp >= query.start_time)

            if query.end_time:
                conditions.append(CaddyAccessLogTbl.timestamp <= query.end_time)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            # 排序和分页
            stmt = stmt.order_by(desc(CaddyAccessLogTbl.timestamp))
            stmt = stmt.limit(query.limit).offset(query.offset)

            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyAccessLog.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_logs_by_ip(client_ip: str, limit: int = 100) -> List[CaddyAccessLog]:
    """
    根据客户端 IP 查询访问日志
    
    Args:
        client_ip: 客户端 IP
        limit: 返回数量限制
        
    Returns:
        访问日志列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl).where(
                CaddyAccessLogTbl.client_ip == client_ip
            ).order_by(desc(CaddyAccessLogTbl.timestamp)).limit(limit)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyAccessLog.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_logs_by_service(upstream_service: str, limit: int = 100) -> List[CaddyAccessLog]:
    """
    根据上游服务查询访问日志
    
    Args:
        upstream_service: 上游服务名称
        limit: 返回数量限制
        
    Returns:
        访问日志列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl).where(
                CaddyAccessLogTbl.upstream_service == upstream_service
            ).order_by(desc(CaddyAccessLogTbl.timestamp)).limit(limit)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyAccessLog.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_waf_blocked_logs(limit: int = 100) -> List[CaddyAccessLog]:
    """
    查询被 WAF 阻止的访问日志
    
    Args:
        limit: 返回数量限制
        
    Returns:
        访问日志列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl).where(
                CaddyAccessLogTbl.waf_action == 'block'
            ).order_by(desc(CaddyAccessLogTbl.timestamp)).limit(limit)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyAccessLog.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_rate_limited_logs(limit: int = 100) -> List[CaddyAccessLog]:
    """
    查询被限流的访问日志
    
    Args:
        limit: 返回数量限制
        
    Returns:
        访问日志列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyAccessLogTbl).where(
                CaddyAccessLogTbl.rate_limited == True
            ).order_by(desc(CaddyAccessLogTbl.timestamp)).limit(limit)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyAccessLog.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_country_distribution(start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[
    Dict[str, Any]]:
    """
    获取访问日志的国家分布统计
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        国家分布列表 [{"country": "中国", "count": 100}, ...]
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(
                CaddyAccessLogTbl.country,
                CaddyAccessLogTbl.country_code,
                func.count(CaddyAccessLogTbl.id).label('count')
            ).where(_build_non_internal_traffic_condition()).group_by(
                CaddyAccessLogTbl.country,
                CaddyAccessLogTbl.country_code,
            )

            # 时间范围过滤
            if start_time:
                stmt = stmt.where(CaddyAccessLogTbl.timestamp >= start_time)
            if end_time:
                stmt = stmt.where(CaddyAccessLogTbl.timestamp <= end_time)

            stmt = stmt.order_by(desc('count'))

            rows = (await session.execute(stmt)).all()
            return [
                {
                    "country": r.country,
                    "country_code": r.country_code,
                    "count": r.count,
                }
                for r in rows
            ] if rows else []


async def get_ip_distribution(start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[
    Dict[str, Any]]:
    """
    获取访问日志的 IP 分布统计

    Args:
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        IP 分布列表 [{"client_ip": "1.2.3.4", "count": 100}, ...]
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(
                CaddyAccessLogTbl.client_ip,
                CaddyAccessLogTbl.country,
                CaddyAccessLogTbl.city,
                func.count(CaddyAccessLogTbl.id).label('count')
            ).where(_build_non_internal_traffic_condition()).group_by(
                CaddyAccessLogTbl.client_ip,
                CaddyAccessLogTbl.country,
                CaddyAccessLogTbl.city,
            )

            if start_time:
                stmt = stmt.where(CaddyAccessLogTbl.timestamp >= start_time)
            if end_time:
                stmt = stmt.where(CaddyAccessLogTbl.timestamp <= end_time)

            stmt = stmt.order_by(desc('count'))

            rows = (await session.execute(stmt)).all()
            return [
                {
                    "client_ip": r.client_ip,
                    "country": r.country,
                    "city": r.city,
                    "count": r.count,
                }
                for r in rows
            ] if rows else []


async def get_status_code_distribution(start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> \
List[Dict[str, Any]]:
    """
    获取状态码分布统计
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        状态码分布列表 [{"status_code": 200, "count": 1000}, ...]
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(
                CaddyAccessLogTbl.status_code,
                func.count(CaddyAccessLogTbl.id).label('count')
            ).where(
                _build_non_internal_traffic_condition()
            ).group_by(CaddyAccessLogTbl.status_code)

            # 时间范围过滤
            if start_time:
                stmt = stmt.where(CaddyAccessLogTbl.timestamp >= start_time)
            if end_time:
                stmt = stmt.where(CaddyAccessLogTbl.timestamp <= end_time)

            stmt = stmt.order_by(CaddyAccessLogTbl.status_code)

            rows = (await session.execute(stmt)).all()
            return [{"status_code": r.status_code, "count": r.count} for r in rows] if rows else []


async def get_timeseries_distribution(
        stat_period: str,
        start_time: datetime,
        end_time: datetime,
        upstream_service: Optional[str] = None,
        matched_route: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按时间粒度聚合访问日志
    Aggregate access logs by time bucket for trend analysis

    Args:
        stat_period: 时间粒度（minute/hour/day/month）
        start_time: 开始时间
        end_time: 结束时间
        upstream_service: 可选服务过滤
        matched_route: 可选路由过滤

    Returns:
        聚合结果列表，每项包含 bucket_time 与统计字段
    """
    valid_periods = {"minute", "hour", "day", "month"}
    if stat_period not in valid_periods:
        raise ValueError(f"Invalid stat_period: {stat_period}, expected one of {sorted(valid_periods)}")

    async with Rmanager.pg_session() as session:
        async with session.begin():
            bucket_time = func.date_trunc(stat_period, CaddyAccessLogTbl.timestamp).label("bucket_time")

            success_count = func.sum(
                case((CaddyAccessLogTbl.status_code.between(200, 399), 1), else_=0)
            ).label("success_requests")
            client_error_count = func.sum(
                case((CaddyAccessLogTbl.status_code.between(400, 499), 1), else_=0)
            ).label("client_error_requests")
            server_error_count = func.sum(
                case((CaddyAccessLogTbl.status_code.between(500, 599), 1), else_=0)
            ).label("server_error_requests")
            waf_blocked_count = func.sum(
                case((CaddyAccessLogTbl.waf_action == "block", 1), else_=0)
            ).label("waf_blocked_requests")
            waf_logged_count = func.sum(
                case((CaddyAccessLogTbl.waf_action == "log", 1), else_=0)
            ).label("waf_logged_requests")
            rate_limited_count = func.sum(
                case((CaddyAccessLogTbl.rate_limited.is_(True), 1), else_=0)
            ).label("rate_limited_requests")
            tls_count = func.sum(
                case((CaddyAccessLogTbl.tls_version.is_not(None), 1), else_=0)
            ).label("tls_requests")

            stmt = select(
                bucket_time,
                func.count(CaddyAccessLogTbl.id).label("total_requests"),
                success_count,
                client_error_count,
                server_error_count,
                func.coalesce(func.sum(CaddyAccessLogTbl.response_size), 0).label("total_bytes_sent"),
                func.coalesce(func.avg(CaddyAccessLogTbl.response_time), None).label("avg_response_time"),
                func.coalesce(func.min(CaddyAccessLogTbl.response_time), None).label("min_response_time"),
                func.coalesce(func.max(CaddyAccessLogTbl.response_time), None).label("max_response_time"),
                func.percentile_cont(0.5).within_group(CaddyAccessLogTbl.response_time).label("p50_response_time"),
                func.percentile_cont(0.95).within_group(CaddyAccessLogTbl.response_time).label("p95_response_time"),
                func.percentile_cont(0.99).within_group(CaddyAccessLogTbl.response_time).label("p99_response_time"),
                waf_blocked_count,
                waf_logged_count,
                rate_limited_count,
                tls_count,
                func.count(func.distinct(CaddyAccessLogTbl.client_ip)).label("unique_ips"),
                func.count(func.distinct(CaddyAccessLogTbl.user_agent)).label("unique_user_agents"),
            ).where(
                and_(
                    CaddyAccessLogTbl.timestamp >= start_time,
                    CaddyAccessLogTbl.timestamp <= end_time,
                    _build_non_internal_traffic_condition(),
                )
            )

            if upstream_service:
                stmt = stmt.where(CaddyAccessLogTbl.upstream_service == upstream_service)

            if matched_route:
                stmt = stmt.where(CaddyAccessLogTbl.matched_route == matched_route)

            stmt = stmt.group_by(bucket_time).order_by(bucket_time)

            rows = (await session.execute(stmt)).all()

            result: List[Dict[str, Any]] = []
            for row in rows:
                total_requests = int(row.total_requests or 0)
                tls_requests = int(row.tls_requests or 0)
                result.append({
                    "bucket_time": row.bucket_time,
                    "total_requests": total_requests,
                    "success_requests": int(row.success_requests or 0),
                    "client_error_requests": int(row.client_error_requests or 0),
                    "server_error_requests": int(row.server_error_requests or 0),
                    "total_bytes_sent": int(row.total_bytes_sent or 0),
                    "avg_response_time": int(row.avg_response_time) if row.avg_response_time is not None else None,
                    "min_response_time": int(row.min_response_time) if row.min_response_time is not None else None,
                    "max_response_time": int(row.max_response_time) if row.max_response_time is not None else None,
                    "p50_response_time": int(row.p50_response_time) if row.p50_response_time is not None else None,
                    "p95_response_time": int(row.p95_response_time) if row.p95_response_time is not None else None,
                    "p99_response_time": int(row.p99_response_time) if row.p99_response_time is not None else None,
                    "waf_blocked_requests": int(row.waf_blocked_requests or 0),
                    "waf_logged_requests": int(row.waf_logged_requests or 0),
                    "rate_limited_requests": int(row.rate_limited_requests or 0),
                    "tls_requests": tls_requests,
                    "non_tls_requests": max(0, total_requests - tls_requests),
                    "unique_ips": int(row.unique_ips or 0),
                    "unique_user_agents": int(row.unique_user_agents or 0),
                })

            return result


async def delete_old_logs(before_time: datetime) -> int:
    """
    删除指定时间之前的访问日志
    
    Args:
        before_time: 删除此时间之前的日志
        
    Returns:
        删除的记录数
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyAccessLogTbl).where(CaddyAccessLogTbl.timestamp < before_time)
            result = await session.execute(stmt)
            return result.rowcount


async def count_access_logs(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    统计访问日志数量
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        日志数量
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(func.count(CaddyAccessLogTbl.id))

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyAccessLogTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyAccessLogTbl, key) == value)

            count = (await session.execute(stmt)).scalar_one()
            return count

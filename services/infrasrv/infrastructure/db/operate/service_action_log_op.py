"""
服务行为日志表数据库操作
"""
from typing import (
    List,
    Optional,
    Dict,
    Any,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import itertools

from sqlalchemy import (
    select,
    desc,
)
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager

from cancan_microstack.public.schemas.infra.service_action_log import (
    ServiceActionLog,
    ServiceActionLogCreate
)
from cancan_microstack.services.infrasrv.infrastructure.db.model.service_action_log_tbl import ServiceActionLogTbl


async def create_action_log(data: ServiceActionLogCreate) -> ServiceActionLog:
    """
    创建服务行为日志
    
    Args:
        data: 日志数据
    
    Returns:
        创建的日志记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            values_dict = data.model_dump()
            stmt = insert(ServiceActionLogTbl).values(**values_dict).returning(ServiceActionLogTbl)
            row = (await session.execute(stmt)).scalar_one()
            return ServiceActionLog.model_validate(row, from_attributes=True)


async def create_action_logs_batch(logs: List[ServiceActionLogCreate]) -> None:
    """
    批量创建服务行为日志
    
    Args:
        logs: 日志数据列表
    """
    if not logs:
        return

    async with Rmanager.pg_session() as session:
        batched_iter = itertools.batched(logs, 500)  # 每批500条
        for chunk in batched_iter:
            async with session.begin():
                values_list = [log.model_dump() for log in chunk]
                stmt = insert(ServiceActionLogTbl).values(values_list)
                await session.execute(stmt)


async def insert_service_action_log(
        *,
        service_name: str,
        action_type: str,
        action_status: str,
        instance_id: Optional[str] = None,
        action_detail: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        triggered_by: str = "system",
        action_metadata: Optional[Dict[str, Any]] = None,
) -> ServiceActionLog:
    """Convenience wrapper to insert a single action log entry."""
    payload = ServiceActionLogCreate(
        service_name=service_name,
        instance_id=instance_id,
        action_type=action_type,
        action_status=action_status,
        action_detail=action_detail,
        error_message=error_message,
        triggered_by=triggered_by,
        action_metadata=action_metadata,
    )
    return await create_action_log(payload)


async def get_action_logs(
        service_name: Optional[str] = None,
        instance_id: Optional[str] = None,
        action_type: Optional[str] = None,
        action_status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
) -> List[ServiceActionLog]:
    """
    查询服务行为日志（支持多条件过滤）
    
    Args:
        service_name: 服务名称过滤
        instance_id: 实例ID过滤
        action_type: 行为类型过滤
        action_status: 行为状态过滤
        start_time: 开始时间过滤
        end_time: 结束时间过滤
        limit: 返回记录数限制
        offset: 偏移量
    
    Returns:
        日志记录列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceActionLogTbl).where(ServiceActionLogTbl.flag == 0)

            # 动态添加过滤条件
            if service_name:
                stmt = stmt.where(ServiceActionLogTbl.service_name == service_name)
            if instance_id:
                stmt = stmt.where(ServiceActionLogTbl.instance_id == instance_id)
            if action_type:
                stmt = stmt.where(ServiceActionLogTbl.action_type == action_type)
            if action_status:
                stmt = stmt.where(ServiceActionLogTbl.action_status == action_status)
            if start_time:
                stmt = stmt.where(ServiceActionLogTbl.created_time >= start_time)
            if end_time:
                stmt = stmt.where(ServiceActionLogTbl.created_time <= end_time)

            # 按创建时间倒序排列
            stmt = stmt.order_by(desc(ServiceActionLogTbl.created_time))
            stmt = stmt.limit(limit).offset(offset)

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceActionLog.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_recent_action_logs(
        service_name: str,
        hours: int = 24,
        limit: int = 100
) -> List[ServiceActionLog]:
    """
    获取最近N小时的服务行为日志
    
    Args:
        service_name: 服务名称
        hours: 最近几小时
        limit: 返回记录数限制
    
    Returns:
        日志记录列表
    """
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    return await get_action_logs(
        service_name=service_name,
        start_time=start_time,
        limit=limit
    )


async def get_action_log_statistics(
        service_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
) -> dict:
    """
    获取服务行为日志统计信息
    
    Args:
        service_name: 服务名称过滤
        start_time: 开始时间
        end_time: 结束时间
    
    Returns:
        统计信息字典
    """
    logs = await get_action_logs(
        service_name=service_name,
        start_time=start_time,
        end_time=end_time,
        limit=10000  # 获取足够多的记录用于统计
    )

    # 统计各种行为类型的数量
    action_type_count = {}
    action_status_count = {}

    for log in logs:
        # 统计行为类型
        if log.action_type not in action_type_count:
            action_type_count[log.action_type] = 0
        action_type_count[log.action_type] += 1

        # 统计行为状态
        if log.action_status not in action_status_count:
            action_status_count[log.action_status] = 0
        action_status_count[log.action_status] += 1

    return {
        "total_count": len(logs),
        "action_type_count": action_type_count,
        "action_status_count": action_status_count,
    }


async def query_service_action_logs(
        service_name: Optional[str] = None,
        action_type: Optional[str] = None,
        action_status: Optional[str] = None,
        limit: int = 100
) -> List[ServiceActionLog]:
    """
    查询服务行为日志（简化版，供 API 调用）
    
    Args:
        service_name: 服务名称（可选）
        action_type: 操作类型（可选）
        action_status: 操作状态（可选）
        limit: 返回数量限制
    
    Returns:
        服务行为日志列表
    """
    return await get_action_logs(
        service_name=service_name,
        action_type=action_type,
        action_status=action_status,
        limit=limit,
        offset=0
    )

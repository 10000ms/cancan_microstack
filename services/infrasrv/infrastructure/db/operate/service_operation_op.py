"""
服务操作记录表数据库操作函数
"""
from typing import (
    List,
    Optional,
    Sequence,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from sqlalchemy import (
    select,
    update,
    and_,
)
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_operation import (
    ServiceOperation,
    ServiceOperationCreate,
    ServiceOperationUpdate,
    ServiceOperationQuery,
)
from cancan_microstack.services.infrasrv.infrastructure.db.model.service_operation_tbl import ServiceOperationTbl


async def get_operation_by_id(operation_id: str) -> Optional[ServiceOperation]:
    """
    根据操作ID查询操作记录
    
    Args:
        operation_id: 操作ID
    
    Returns:
        操作记录，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceOperationTbl).where(
                and_(
                    ServiceOperationTbl.operation_id == operation_id,
                    ServiceOperationTbl.flag == 0
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceOperation.model_validate(row, from_attributes=True) if row else None


async def create_operation(data: ServiceOperationCreate) -> ServiceOperation:
    """
    创建服务操作记录
    
    Args:
        data: 操作数据
    
    Returns:
        创建的操作记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            values_dict = data.model_dump()

            # 幂等创建：遇到重复 operation_id 时直接返回已有记录
            # Idempotent create: return existing record when operation_id already exists
            stmt = (
                insert(ServiceOperationTbl)
                .values(**values_dict)
                .on_conflict_do_nothing(index_elements=[ServiceOperationTbl.operation_id])
                .returning(ServiceOperationTbl)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return ServiceOperation.model_validate(row, from_attributes=True)

            existing_stmt = select(ServiceOperationTbl).where(
                and_(
                    ServiceOperationTbl.operation_id == data.operation_id,
                    ServiceOperationTbl.flag == 0,
                )
            )
            existing_row = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing_row:
                return ServiceOperation.model_validate(existing_row, from_attributes=True)

            raise RuntimeError(f"Operation record not found after insert conflict: {data.operation_id}")


async def update_operation(operation_id: str, data: ServiceOperationUpdate) -> Optional[ServiceOperation]:
    """
    更新服务操作记录
    
    Args:
        operation_id: 操作ID
        data: 更新数据
    
    Returns:
        更新后的操作记录，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 构建更新字典，只包含非 None 的字段
            update_dict = {k: v for k, v in data.model_dump().items() if v is not None}

            if not update_dict:
                return await get_operation_by_id(operation_id)

            stmt = (
                update(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.operation_id == operation_id,
                        ServiceOperationTbl.flag == 0
                    )
                )
                .values(**update_dict)
                .returning(ServiceOperationTbl)
            )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return ServiceOperation.model_validate(row, from_attributes=True) if row else None


async def query_operations(query: ServiceOperationQuery) -> List[ServiceOperation]:
    """
    查询服务操作记录列表
    
    Args:
        query: 查询条件
    
    Returns:
        操作记录列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceOperationTbl).where(ServiceOperationTbl.flag == 0)

            # 动态添加查询条件
            if query.operation_id:
                stmt = stmt.where(ServiceOperationTbl.operation_id == query.operation_id)
            if query.service_name:
                stmt = stmt.where(ServiceOperationTbl.service_name == query.service_name)
            if query.operation_type:
                stmt = stmt.where(ServiceOperationTbl.operation_type == query.operation_type)
            if query.status:
                stmt = stmt.where(ServiceOperationTbl.status == query.status)

            # 排序：最新的在前
            stmt = stmt.order_by(ServiceOperationTbl.created_time.desc())

            # 分页
            stmt = stmt.limit(query.limit).offset(query.offset)

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceOperation.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_pending_operations(limit: int = 100) -> List[ServiceOperation]:
    """
    获取所有待处理的操作
    
    用于后台任务队列消费。
    
    Args:
        limit: 最大返回数量
    
    Returns:
        待处理操作列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                select(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.status == 'pending',
                        ServiceOperationTbl.flag == 0
                    )
                )
                .order_by(ServiceOperationTbl.created_time.asc())
                .limit(limit)
            )

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceOperation.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_operations_for_polling(
        *,
        statuses: Sequence[str],
        max_age_minutes: int,
        limit: int = 100,
) -> List[ServiceOperation]:
    """获取需要轮询的操作 / Fetch operations that still require polling"""

    if not statuses:
        return []

    async with Rmanager.pg_session() as session:
        async with session.begin():
            threshold = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
            stmt = (
                select(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.status.in_(list(statuses)),
                        ServiceOperationTbl.flag == 0,
                        ServiceOperationTbl.created_time >= threshold,
                    )
                )
                .order_by(ServiceOperationTbl.created_time.asc())
                .limit(limit)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceOperation.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_stale_operations(
        *,
        statuses: Sequence[str],
        older_than_minutes: int,
        limit: int = 100,
) -> List[ServiceOperation]:
    """获取超时未完成的操作 / Fetch operations that exceeded the allowed window"""

    if not statuses:
        return []

    async with Rmanager.pg_session() as session:
        async with session.begin():
            threshold = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
            stmt = (
                select(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.status.in_(list(statuses)),
                        ServiceOperationTbl.flag == 0,
                        ServiceOperationTbl.created_time < threshold,
                    )
                )
                .order_by(ServiceOperationTbl.created_time.asc())
                .limit(limit)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceOperation.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_timeout_operations(timeout_minutes: int = 10) -> List[ServiceOperation]:
    """
    获取超时的操作（状态为 running 但超过指定时间未完成）
    
    Args:
        timeout_minutes: 超时时间（分钟）
    
    Returns:
        超时操作列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

            stmt = (
                select(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.status == 'running',
                        ServiceOperationTbl.started_at < timeout_threshold,
                        ServiceOperationTbl.flag == 0
                    )
                )
                .order_by(ServiceOperationTbl.started_at.asc())
            )

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceOperation.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_recent_operations_by_service(
        service_name: str,
        status: Optional[str] = None,
        time_window_seconds: int = 300
) -> List[ServiceOperation]:
    """
    获取服务最近的操作记录
    
    用于健康检查时判断服务是否在操作期间（豁免检查）。
    
    Args:
        service_name: 服务名称
        status: 操作状态过滤，None 表示不过滤
        time_window_seconds: 时间窗口（秒），默认5分钟
    
    Returns:
        最近的操作记录列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            time_threshold = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)

            stmt = (
                select(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.service_name == service_name,
                        ServiceOperationTbl.created_time >= time_threshold,
                        ServiceOperationTbl.flag == 0
                    )
                )
            )

            if status:
                stmt = stmt.where(ServiceOperationTbl.status == status)

            stmt = stmt.order_by(ServiceOperationTbl.created_time.desc())

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceOperation.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def increment_retry_count(operation_id: str) -> Optional[ServiceOperation]:
    """
    增加操作的重试次数
    
    Args:
        operation_id: 操作ID
    
    Returns:
        更新后的操作记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.operation_id == operation_id,
                        ServiceOperationTbl.flag == 0
                    )
                )
                .values(
                    retry_count=ServiceOperationTbl.retry_count + 1,
                    last_retry_at=datetime.now(timezone.utc)
                )
                .returning(ServiceOperationTbl)
            )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return ServiceOperation.model_validate(row, from_attributes=True) if row else None


async def delete_old_operations(days: int = 30) -> int:
    """
    删除旧的操作记录（软删除）
    
    用于定期清理历史数据。
    
    Args:
        days: 保留天数，超过此天数的记录将被删除
    
    Returns:
        删除的记录数
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

            stmt = (
                update(ServiceOperationTbl)
                .where(
                    and_(
                        ServiceOperationTbl.created_time < threshold_date,
                        ServiceOperationTbl.flag == 0
                    )
                )
                .values(flag=1)
            )

            result = await session.execute(stmt)
            return result.rowcount

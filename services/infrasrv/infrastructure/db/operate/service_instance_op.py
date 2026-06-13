"""
服务实例表数据库操作函数
"""
from typing import (
    List,
    Optional,
)
from datetime import datetime, timezone
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_instance import (
    ServiceInstance,
    ServiceInstanceCreate,
    ServiceInstanceUpdate,
    ServiceInstanceQuery,
)
from cancan_microstack.services.infrasrv.infrastructure.db.model.service_instance_tbl import ServiceInstanceTbl


async def get_instance_by_id(instance_id: str) -> Optional[ServiceInstance]:
    """
    根据实例ID查询实例信息
    
    Args:
        instance_id: 实例ID
    
    Returns:
        实例信息，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(
                and_(
                    ServiceInstanceTbl.instance_id == instance_id,
                    ServiceInstanceTbl.flag == 0
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def get_instance_by_container_name(container_name: str) -> Optional[ServiceInstance]:
    """
    根据容器名查询实例信息
    
    Args:
        container_name: 容器名称
    
    Returns:
        实例信息，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(
                and_(
                    ServiceInstanceTbl.container_name == container_name,
                    ServiceInstanceTbl.flag == 0
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def insert_instance(data: ServiceInstanceCreate) -> ServiceInstance:
    """
    创建服务实例记录（插入实例）
    
    Args:
        data: 实例数据
    
    Returns:
        创建的实例记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(ServiceInstanceTbl).values(data.model_dump()).returning(ServiceInstanceTbl)
            row = (await session.execute(stmt)).scalar_one()
            return ServiceInstance.model_validate(row, from_attributes=True)


async def create_instance(data: ServiceInstanceCreate) -> ServiceInstance:
    """
    Alias of `insert_instance`.
    Delegates to `insert_instance` which implements the actual insertion logic.
    """
    return await insert_instance(data)


async def upsert_instance(data: ServiceInstanceCreate) -> ServiceInstance:
    """插入或更新服务实例，保持实例唯一 / Upsert a service instance row."""

    payload = data.model_dump()
    now_utc = datetime.now(timezone.utc)
    payload.setdefault("status", "UP")
    payload.setdefault("expected_status", "UP")
    payload.setdefault("health_status", data.health_status or "unknown")
    payload.setdefault("last_heartbeat", now_utc)

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                insert(ServiceInstanceTbl)
                .values(**payload)
                .returning(ServiceInstanceTbl)
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ServiceInstanceTbl.instance_id],
                set_={
                    "service_name": stmt.excluded.service_name,
                    "container_name": stmt.excluded.container_name,
                    "compose_service_name": stmt.excluded.compose_service_name,
                    "host": stmt.excluded.host,
                    "port": stmt.excluded.port,
                    "internal_port": stmt.excluded.internal_port,
                    "status": "UP",
                    "expected_status": stmt.excluded.expected_status,
                    "health_check_url": stmt.excluded.health_check_url,
                    "health_status": stmt.excluded.health_status,
                    "instance_metadata": stmt.excluded.instance_metadata,
                    "last_heartbeat": now_utc,
                    "flag": 0,
                }
            )
            row = (await session.execute(stmt)).scalar_one()
            return ServiceInstance.model_validate(row, from_attributes=True)


async def update_instance(instance_id: str, data: ServiceInstanceUpdate) -> Optional[ServiceInstance]:
    """
    更新服务实例记录
    
    Args:
        instance_id: 实例ID
        data: 更新数据
    
    Returns:
        更新后的实例记录，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 构建更新字典，只包含非 None 的字段
            update_dict = {k: v for k, v in data.model_dump().items() if v is not None}

            if not update_dict:
                return await get_instance_by_id(instance_id)

            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(**update_dict)
                .returning(ServiceInstanceTbl)
            )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def query_instances(query: ServiceInstanceQuery) -> List[ServiceInstance]:
    """
    查询服务实例列表
    
    Args:
        query: 查询条件
    
    Returns:
        实例列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(ServiceInstanceTbl.flag == 0)

            # 动态添加查询条件
            if query.service_name:
                stmt = stmt.where(ServiceInstanceTbl.service_name == query.service_name)
            if query.instance_id:
                stmt = stmt.where(ServiceInstanceTbl.instance_id == query.instance_id)
            if query.status:
                stmt = stmt.where(ServiceInstanceTbl.status == query.status)
            if query.expected_status:
                stmt = stmt.where(ServiceInstanceTbl.expected_status == query.expected_status)
            if query.health_status:
                stmt = stmt.where(ServiceInstanceTbl.health_status == query.health_status)

            # 排序：按创建时间升序（实例0在前）
            stmt = stmt.order_by(ServiceInstanceTbl.instance_id.asc())

            # 分页
            stmt = stmt.limit(query.limit).offset(query.offset)

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def list_instances_by_service(service_name: str) -> List[ServiceInstance]:
    """
    获取服务的所有实例（列出实例）
    
    Args:
        service_name: 服务名称
    
    Returns:
        实例列表
    """
    query = ServiceInstanceQuery(service_name=service_name, limit=1000)
    return await query_instances(query)


async def get_all_instances() -> List[ServiceInstance]:
    """列出所有有效实例 / List every active instance."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(ServiceInstanceTbl.flag == 0)
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_healthy_instances(service_name: str) -> List[ServiceInstance]:
    """
    获取服务的所有健康实例
    
    Args:
        service_name: 服务名称
    
    Returns:
        健康实例列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                select(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.service_name == service_name,
                        ServiceInstanceTbl.status == "UP",
                        ServiceInstanceTbl.health_status == 'healthy',
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .order_by(ServiceInstanceTbl.instance_id.asc())
            )

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_unhealthy_instances(
        consecutive_failures_threshold: int = 3
) -> List[ServiceInstance]:
    """
    获取所有不健康的实例（连续失败次数达到阈值）
    
    Args:
        consecutive_failures_threshold: 连续失败次数阈值
    
    Returns:
        不健康实例列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                select(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.expected_status == "UP",
                        ServiceInstanceTbl.consecutive_failures >= consecutive_failures_threshold,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .order_by(ServiceInstanceTbl.consecutive_failures.desc())
            )

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def increment_failure_count(instance_id: str, error_message: Optional[str] = None) -> Optional[ServiceInstance]:
    """
    增加实例的连续失败次数
    
    Args:
        instance_id: 实例ID
        error_message: 错误信息
    
    Returns:
        更新后的实例记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            update_values = {
                'consecutive_failures': ServiceInstanceTbl.consecutive_failures + 1,
                'health_status': 'unhealthy',
                'last_health_check': datetime.now(timezone.utc),
            }

            if error_message:
                update_values['last_health_error'] = error_message

            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(**update_values)
                .returning(ServiceInstanceTbl)
            )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def mark_instance_status(service_name: str, instance_id: str, status: str) -> None:
    """更新实例状态（含软删除逻辑） / Update instance status marker."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.service_name == service_name,
                        ServiceInstanceTbl.instance_id == instance_id,
                    )
                )
                .values(status=status)
            )
            await session.execute(stmt)


async def soft_delete_instance(service_name: str, instance_id: str) -> None:
    """通过 flag 标记实例为删除状态 / Soft delete instance via flag."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.service_name == service_name,
                        ServiceInstanceTbl.instance_id == instance_id,
                    )
                )
                .values(flag=1, status='DOWN')
            )
            await session.execute(stmt)


async def touch_instance_heartbeat(service_name: str, instance_id: str, status: Optional[str] = None) -> None:
    """更新实例心跳和可选状态 / Update heartbeat timestamp and optionally status."""

    update_fields = {
        'last_heartbeat': datetime.now(timezone.utc),
    }
    if status:
        update_fields['status'] = status

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.service_name == service_name,
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0,
                    )
                )
                .values(**update_fields)
            )
            await session.execute(stmt)


async def reset_failure_count(instance_id: str) -> Optional[ServiceInstance]:
    """
    重置实例的连续失败次数（健康检查成功时调用）
    
    Args:
        instance_id: 实例ID
    
    Returns:
        更新后的实例记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(
                    consecutive_failures=0,
                    health_status='healthy',
                    last_health_check=datetime.now(timezone.utc),
                    last_health_error=None
                )
                .returning(ServiceInstanceTbl)
            )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def increment_restart_count(instance_id: str) -> Optional[ServiceInstance]:
    """
    增加实例的重启次数
    
    Args:
        instance_id: 实例ID
    
    Returns:
        更新后的实例记录
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(restart_count=ServiceInstanceTbl.restart_count + 1)
                .returning(ServiceInstanceTbl)
            )

            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def get_next_available_port(service_name: str, base_port: int = 18000, max_instances: int = 100) -> Optional[int]:
    """
    获取服务的下一个可用端口
    
    Args:
        service_name: 服务名称
        base_port: 基础端口号
        max_instances: 最大实例数
    
    Returns:
        可用端口号，如果没有可用端口则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 查询该服务已使用的端口
            stmt = (
                select(ServiceInstanceTbl.port)
                .where(
                    and_(
                        ServiceInstanceTbl.service_name == service_name,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .order_by(ServiceInstanceTbl.port.asc())
            )

            rows = (await session.execute(stmt)).scalars().all()
            used_ports = set(rows)

            # 查找第一个未使用的端口
            for i in range(max_instances):
                port = base_port + i
                if port not in used_ports:
                    return port

            return None


async def count_instances_by_service(service_name: str, status: Optional[str] = None) -> int:
    """
    统计服务的实例数量
    
    Args:
        service_name: 服务名称
        status: 状态过滤，None 表示不过滤
    
    Returns:
        实例数量
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(func.count()).select_from(ServiceInstanceTbl).where(
                and_(
                    ServiceInstanceTbl.service_name == service_name,
                    ServiceInstanceTbl.flag == 0
                )
            )

            if status:
                stmt = stmt.where(ServiceInstanceTbl.status == status)

            result = await session.execute(stmt)
            return result.scalar_one_or_none() or 0


async def delete_instance_by_id(instance_id: str) -> bool:
    """
    根据ID删除服务实例（软删除）
    
    Args:
        instance_id: 实例ID
    
    Returns:
        是否成功删除
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(flag=1)
            )

            result = await session.execute(stmt)
            return result.rowcount > 0


async def get_instances_by_status(status: str) -> List[ServiceInstance]:
    """
    根据状态查询实例列表
    
    Args:
        status: 实例状态 (running, stopped, starting, stopping等)
    
    Returns:
        实例列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(
                and_(
                    ServiceInstanceTbl.status == status,
                    ServiceInstanceTbl.flag == 0
                )
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def update_instance_health_status(
        instance_id: str,
        health_status: str,
        last_health_check: Optional[datetime] = None,
        last_health_error: Optional[str] = None,
        last_heartbeat: Optional[datetime] = None,
) -> Optional[ServiceInstance]:
    """
    更新实例健康状态
    
    Args:
        instance_id: 实例ID
        health_status: 健康状态 (healthy, degraded, unhealthy)
        last_health_check: 最后健康检查时间
        last_health_error: 最后健康检查错误信息
    
    Returns:
        更新后的实例信息
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            update_data = {"health_status": health_status}
            if last_health_check:
                update_data["last_health_check"] = last_health_check
            if last_health_error is not None:  # 允许设置为 None 清空错误
                update_data["last_health_error"] = last_health_error
            if last_heartbeat:
                update_data["last_heartbeat"] = last_heartbeat

            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(**update_data)
                .returning(ServiceInstanceTbl)
            )

            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def increment_instance_consecutive_failures(instance_id: str) -> Optional[int]:
    """
    递增实例连续失败次数
    
    Args:
        instance_id: 实例ID
    
    Returns:
        更新后的连续失败次数。如果实例不存在，返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(consecutive_failures=ServiceInstanceTbl.consecutive_failures + 1)
                .returning(ServiceInstanceTbl.consecutive_failures)
            )

            result = await session.execute(stmt)
            return result.scalar_one_or_none()


async def reset_instance_consecutive_failures(instance_id: str) -> Optional[ServiceInstance]:
    """
    重置实例连续失败次数
    
    Args:
        instance_id: 实例ID
    
    Returns:
        更新后的实例信息
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInstanceTbl)
                .where(
                    and_(
                        ServiceInstanceTbl.instance_id == instance_id,
                        ServiceInstanceTbl.flag == 0
                    )
                )
                .values(consecutive_failures=0)
                .returning(ServiceInstanceTbl)
            )

            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInstance.model_validate(row, from_attributes=True) if row else None


async def hard_delete_instances_by_ids(instance_ids: List[str]) -> int:
    """
    根据实例ID列表物理删除实例记录
    Hard delete instance records by a list of instance IDs.
    
    Args:
        instance_ids: 要删除的实例ID列表
    
    Returns:
        被删除的记录数量
    """
    if not instance_ids:
        return 0

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                delete(ServiceInstanceTbl)
                .where(ServiceInstanceTbl.instance_id.in_(instance_ids))
            )
            result = await session.execute(stmt)
            return result.rowcount

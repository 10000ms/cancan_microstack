"""
服务信息表数据库操作
"""
from typing import (
    List,
    Optional,
)
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_info import ServiceInfo, ServiceInfoCreate, ServiceInfoUpdate
from cancan_microstack.services.infrasrv.infrastructure.db.model.service_info_tbl import ServiceInfoTbl


async def get_service_info_by_name(service_name: str) -> Optional[ServiceInfo]:
    """
    根据服务名称查询服务信息
    
    Args:
        service_name: 服务名称
    
    Returns:
        服务信息，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl).where(
                and_(
                    ServiceInfoTbl.service_name == service_name,
                    ServiceInfoTbl.flag == 0
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInfo.model_validate(row, from_attributes=True) if row else None


async def get_all_service_info(service_type: Optional[str] = None) -> List[ServiceInfo]:
    """
    获取所有服务信息
    
    Args:
        service_type: 服务类型过滤，None 表示不过滤
    
    Returns:
        服务信息列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl).where(ServiceInfoTbl.flag == 0)
            if service_type:
                stmt = stmt.where(ServiceInfoTbl.service_type == service_type)

            stmt = stmt.order_by(ServiceInfoTbl.created_time.asc())
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInfo.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def create_or_update_service_info(service_name: str, data: ServiceInfoCreate) -> ServiceInfo:
    """
    创建或更新服务信息（UPSERT）
    
    Args:
        service_name: 服务名称
        data: 服务信息数据
    
    Returns:
        创建或更新后的服务信息
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            values_dict = data.model_dump()
            values_dict['service_name'] = service_name

            stmt = insert(ServiceInfoTbl).values(**values_dict)
            stmt = stmt.on_conflict_do_update(
                index_elements=['service_name'],
                set_={
                    'description': stmt.excluded.description,
                    'service_type': stmt.excluded.service_type,
                    'health_check_path': stmt.excluded.health_check_path,
                    'service_metadata': stmt.excluded.service_metadata,
                    'expected_status': stmt.excluded.expected_status,
                    'desired_replicas': stmt.excluded.desired_replicas,
                    'actual_replicas': stmt.excluded.actual_replicas,
                    'scale_policy': stmt.excluded.scale_policy,
                    'last_registered_time': func.current_timestamp(),
                }
            )
            await session.execute(stmt)

            # 查询返回结果
            select_stmt = select(ServiceInfoTbl).where(
                ServiceInfoTbl.service_name == service_name
            )
            row = (await session.execute(select_stmt)).scalar_one()
            return ServiceInfo.model_validate(row, from_attributes=True)


async def update_service_info(service_name: str, data: ServiceInfoUpdate) -> Optional[ServiceInfo]:
    """
    更新服务信息
    
    Args:
        service_name: 服务名称
        data: 更新数据
    
    Returns:
        更新后的服务信息，不存在则返回 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 构建更新字典（只更新非 None 的字段）
            update_dict = {}
            if data.description is not None:
                update_dict['description'] = data.description
            if data.service_type is not None:
                update_dict['service_type'] = data.service_type
            if data.health_check_path is not None:
                update_dict['health_check_path'] = data.health_check_path
            if data.service_metadata is not None:
                update_dict['service_metadata'] = data.service_metadata
            if data.expected_status is not None:
                update_dict['expected_status'] = data.expected_status
            if data.desired_replicas is not None:
                update_dict['desired_replicas'] = data.desired_replicas
            if data.actual_replicas is not None:
                update_dict['actual_replicas'] = data.actual_replicas
            if data.scale_policy is not None:
                update_dict['scale_policy'] = data.scale_policy

            if not update_dict:
                # 没有需要更新的字段，直接返回现有数据
                return await get_service_info_by_name(service_name)

            stmt = update(ServiceInfoTbl).where(
                and_(
                    ServiceInfoTbl.service_name == service_name,
                    ServiceInfoTbl.flag == 0
                )
            ).values(**update_dict)

            result = await session.execute(stmt)
            if result.rowcount == 0:
                return None

            # 查询返回更新后的数据
            return await get_service_info_by_name(service_name)


async def delete_service_info(service_name: str, hard_delete: bool = False) -> bool:
    """
    删除服务信息
    
    Args:
        service_name: 服务名称
        hard_delete: 是否物理删除，False 表示软删除（设置 flag=1）
    
    Returns:
        是否成功删除
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            if hard_delete:
                stmt = delete(ServiceInfoTbl).where(
                    ServiceInfoTbl.service_name == service_name
                )
            else:
                stmt = update(ServiceInfoTbl).where(
                    and_(
                        ServiceInfoTbl.service_name == service_name,
                        ServiceInfoTbl.flag == 0
                    )
                ).values(flag=1)

            result = await session.execute(stmt)
            return result.rowcount > 0


async def update_expected_status(service_name: str, expected_status: str) -> Optional[ServiceInfo]:
    """
    更新服务的期望状态
    
    用于服务启动/停止操作，更新期望状态供健康检查判断。
    
    Args:
        service_name: 服务名称
        expected_status: 期望状态 (running|stopped)
    
    Returns:
        更新后的服务信息
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(ServiceInfoTbl)
                .where(
                    and_(
                        ServiceInfoTbl.service_name == service_name,
                        ServiceInfoTbl.flag == 0
                    )
                )
                .values(expected_status=expected_status)
            )

            result = await session.execute(stmt)
            if result.rowcount == 0:
                return None

            return await get_service_info_by_name(service_name)


async def update_service_replicas(
        service_name: str,
        desired_replicas: Optional[int] = None,
        actual_replicas: Optional[int] = None
) -> Optional[ServiceInfo]:
    """
    更新服务记录中的副本数列（仅写库，不扩缩容）

    仅更新 service_info 表的 desired_replicas / actual_replicas（及 last_scale_at）列，
    用于记录期望/实际副本数。不会增减真实运行容器。

    Args:
        service_name: 服务名称
        desired_replicas: 期望副本数（仅记录）
        actual_replicas: 实际副本数（由上游上报回填）

    Returns:
        更新后的服务信息
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            update_dict = {}

            if desired_replicas is not None:
                update_dict['desired_replicas'] = desired_replicas
                update_dict['last_scale_at'] = func.current_timestamp()

            if actual_replicas is not None:
                update_dict['actual_replicas'] = actual_replicas

            if not update_dict:
                return await get_service_info_by_name(service_name)

            stmt = (
                update(ServiceInfoTbl)
                .where(
                    and_(
                        ServiceInfoTbl.service_name == service_name,
                        ServiceInfoTbl.flag == 0
                    )
                )
                .values(**update_dict)
            )

            result = await session.execute(stmt)
            if result.rowcount == 0:
                return None

            return await get_service_info_by_name(service_name)


async def get_services_with_scale_mismatch() -> List[ServiceInfo]:
    """
    获取期望副本数与实际副本数不一致的服务
    
    用于监控和自动伸缩。
    
    Returns:
        副本数不匹配的服务列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                select(ServiceInfoTbl)
                .where(
                    and_(
                        ServiceInfoTbl.desired_replicas != ServiceInfoTbl.actual_replicas,
                        ServiceInfoTbl.flag == 0
                    )
                )
            )

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInfo.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def list_service_names() -> List[str]:
    """列出所有服务名称 / List all service identifiers."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl.service_name).where(ServiceInfoTbl.flag == 0).order_by(
                ServiceInfoTbl.service_name.asc())
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows) if rows else []

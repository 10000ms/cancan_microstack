"""
服务信息表数据库操作
"""
from typing import (
    List,
    Optional,
)
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_info import ServiceInfo, ServiceInfoCreate
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.service_info_tbl import ServiceInfoTbl


async def get_service_info(service_name: str) -> Optional[ServiceInfo]:
    """
    根据服务名获取服务信息
    
    Args:
        service_name: 服务名称
    
    Returns:
        服务信息对象，如果不存在则返回 None
    """
    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl).where(
                ServiceInfoTbl.service_name == service_name,
                ServiceInfoTbl.flag == 0
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInfo.model_validate(row, from_attributes=True) if row else None


async def get_all_service_info() -> List[ServiceInfo]:
    """
    获取所有服务信息
    
    Returns:
        服务信息列表
    """
    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl).where(ServiceInfoTbl.flag == 0)
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInfo.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def insert_service_info(data: ServiceInfoCreate) -> ServiceInfo:
    """
    插入服务信息（如果已存在则更新）
    
    Args:
        data: 服务信息创建数据
    
    Returns:
        创建或更新的服务信息
    """
    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            values_dict = data.model_dump()
            stmt = insert(ServiceInfoTbl).values(**values_dict).returning(ServiceInfoTbl)
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
            row = (await session.execute(stmt)).scalar_one()
            return ServiceInfo.model_validate(row, from_attributes=True)

"""Read-only service instance queries for opsbff."""
from typing import (
    List,
    Optional,
)

from sqlalchemy import select, and_

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_instance import ServiceInstance
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.service_instance_tbl import ServiceInstanceTbl


async def get_service_instances(
        service_name: str,
        status: Optional[str] = None,
) -> List[ServiceInstance]:
    """获取指定服务的全部实例 / Fetch all instances for a service."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(
                and_(
                    ServiceInstanceTbl.service_name == service_name,
                    ServiceInstanceTbl.flag == 0,
                )
            )
            if status:
                stmt = stmt.where(ServiceInstanceTbl.status == status)

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_all_instances() -> List[ServiceInstance]:
    """读取全部实例数据 / Fetch every instance (ops view)."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(ServiceInstanceTbl.flag == 0)
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_instance(service_name: str, instance_id: str) -> Optional[ServiceInstance]:
    """根据服务名+实例ID读取单条记录 / Fetch a single instance."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(
                and_(
                    ServiceInstanceTbl.service_name == service_name,
                    ServiceInstanceTbl.instance_id == instance_id,
                    ServiceInstanceTbl.flag == 0,
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return ServiceInstance.model_validate(row, from_attributes=True) if row else None

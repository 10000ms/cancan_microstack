"""opsbffsrv service registry data access."""
from typing import (
    List,
    Optional,
)

from sqlalchemy import select, and_

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.enums import ServiceType
from cancan_microstack.public.schemas.infra.service_info import ServiceInfo
from cancan_microstack.public.schemas.infra.service_registry import ServiceMetadata
from cancan_microstack.public.schemas.infra.service_instance import ServiceInstance
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.service_info_tbl import ServiceInfoTbl
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.service_instance_tbl import ServiceInstanceTbl


def _service_info_to_metadata(row: ServiceInfoTbl) -> ServiceMetadata:
    """将 ServiceInfo ORM 记录转换为 ServiceMetadata / Orchestrate metadata view."""

    data = ServiceInfo.model_validate(row, from_attributes=True)
    metadata_bag = dict(data.service_metadata or {})
    owner = metadata_bag.get("owner")
    deploy_region = metadata_bag.get("deploy_region")
    config_version = metadata_bag.get("config_version")

    service_type = data.service_type
    if not isinstance(service_type, ServiceType):
        service_type = ServiceType(service_type)

    return ServiceMetadata(
        service_name=data.service_name,
        description=data.description,
        service_type=service_type,
        owner=owner,
        health_check_path=data.health_check_path,
        deploy_region=deploy_region,
        config_version=config_version,
        service_metadata=metadata_bag,
        expected_status=data.expected_status,
        desired_replicas=data.desired_replicas,
        actual_replicas=data.actual_replicas,
        last_scale_at=data.last_scale_at,
        scale_policy=data.scale_policy,
        registered_time=data.registered_time,
        last_registered_time=data.last_registered_time,
        created_time=data.created_time,
        update_time=data.update_time,
    )


async def get_service_metadata(service_name: str) -> Optional[ServiceMetadata]:
    """获取指定服务的元数据 / Fetch metadata for a single service."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl).where(
                and_(
                    ServiceInfoTbl.service_name == service_name,
                    ServiceInfoTbl.flag == 0,
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return _service_info_to_metadata(row) if row else None


async def get_service_instances(
        service_name: str,
        status: Optional[str] = None,
    health_status: Optional[str] = None,
) -> List[ServiceInstance]:
    """获取指定服务的实例列表 / Fetch instances for a single service."""

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
            if health_status:
                stmt = stmt.where(ServiceInstanceTbl.health_status == health_status)

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_service_by_instance(
        service_name: str,
        instance_id: str,
) -> Optional[ServiceInstance]:
    """根据服务名 + 实例ID 查询单条实例 / Fetch a concrete instance row."""

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


async def get_all_services() -> List[ServiceInstance]:
    """列出全部服务实例 / List every active service instance."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInstanceTbl).where(ServiceInstanceTbl.flag == 0)
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_all_service_names() -> List[str]:
    """获取所有服务名称 / Fetch distinct service names."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl.service_name).where(ServiceInfoTbl.flag == 0).order_by(
                ServiceInfoTbl.service_name.asc())
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows) if rows else []


async def list_service_metadata() -> List[ServiceMetadata]:
    """列出服务级元数据 / Return service metadata rows."""

    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceInfoTbl).where(ServiceInfoTbl.flag == 0)
            rows = list((await session.execute(stmt)).scalars().all())
            return [_service_info_to_metadata(r) for r in rows]

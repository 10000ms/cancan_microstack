from typing import (
    List,
    Optional,
)

from cancan_microstack.public.schemas.infra.enums import ServiceType
from cancan_microstack.public.schemas.infra.service_info import ServiceInfo, ServiceInfoCreate, ServiceInfoUpdate
from cancan_microstack.public.schemas.infra.service_registry import (
    ServiceMetadata,
    ServiceMetadataUpdate,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_info_op import (
    create_or_update_service_info,
    update_service_info,
    get_service_info_by_name,
    get_all_service_info,
    list_service_names as list_service_names_from_info,
)


def _metadata_to_create(metadata: ServiceMetadata) -> ServiceInfoCreate:
    """将 ServiceMetadata 转换为 ServiceInfoCreate / Convert metadata to create payload."""

    metadata_bag = dict(metadata.service_metadata or {})
    for key, value in (
            ("owner", metadata.owner),
            ("deploy_region", metadata.deploy_region),
            ("config_version", metadata.config_version),
    ):
        if value is not None:
            metadata_bag[key] = value

    return ServiceInfoCreate(
        service_name=metadata.service_name,
        description=metadata.description,
        service_type=metadata.service_type.value,
        health_check_path=metadata.health_check_path,
        service_metadata=metadata_bag,
        desired_replicas=metadata.desired_replicas,
        actual_replicas=metadata.actual_replicas,
        expected_status=metadata.expected_status,
        scale_policy=metadata.scale_policy,
    )


def _metadata_update_to_service_info(payload: ServiceMetadataUpdate) -> ServiceInfoUpdate:
    """转换更新请求 / Convert metadata update payload."""

    metadata_updates = dict(payload.service_metadata or {})
    for key, value in (
            ("owner", payload.owner),
            ("deploy_region", payload.deploy_region),
            ("config_version", payload.config_version),
    ):
        if value is not None:
            metadata_updates[key] = value

    return ServiceInfoUpdate(
        description=payload.description,
        health_check_path=payload.health_check_path,
        service_metadata=metadata_updates or None,
        expected_status=payload.expected_status,
        desired_replicas=payload.desired_replicas,
        actual_replicas=payload.actual_replicas,
        scale_policy=payload.scale_policy,
    )


def _info_to_metadata(data: ServiceInfo) -> ServiceMetadata:
    """ServiceInfo -> ServiceMetadata (enum aware)."""

    metadata_bag = dict(data.service_metadata or {})
    return ServiceMetadata(
        service_name=data.service_name,
        description=data.description,
        service_type=ServiceType(data.service_type) if not isinstance(data.service_type,
                                                                      ServiceType) else data.service_type,
        owner=metadata_bag.get("owner"),
        health_check_path=data.health_check_path,
        deploy_region=metadata_bag.get("deploy_region"),
        config_version=metadata_bag.get("config_version"),
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


async def upsert_service_metadata(metadata: ServiceMetadata) -> None:
    """插入或更新服务级元数据 / Upsert service-level metadata."""

    await create_or_update_service_info(metadata.service_name, _metadata_to_create(metadata))


async def update_service_metadata(payload: ServiceMetadataUpdate) -> None:
    """局部更新服务元数据 / Partial update for service metadata."""

    await update_service_info(payload.service_name, _metadata_update_to_service_info(payload))


async def get_service_metadata(service_name: str) -> Optional[ServiceMetadata]:
    """根据名称获取服务元数据 / Fetch a service metadata record by name."""

    record = await get_service_info_by_name(service_name)
    return _info_to_metadata(record) if record else None


async def list_service_metadata() -> List[ServiceMetadata]:
    """获取所有服务元数据 / List all registered services."""

    records = await get_all_service_info()
    return [_info_to_metadata(item) for item in records]


async def list_service_names() -> List[str]:
    """获取所有服务名称 / List all service names."""

    return await list_service_names_from_info()

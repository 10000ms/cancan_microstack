"""
服务注册查询领域层
负责为ops前端提供服务实例的查询功能
不包含服务注册/注销/心跳等写操作（由infrasrv负责）
说明：本服务直接从数据库读取由 infrasrv 维护的服务状态，不执行任何独立的健康检查或陈旧实例过滤。
"""
from typing import (
    List,
    Dict,
)
from datetime import (
    datetime,
    timezone,
)

from cancan_microstack.public.const.health_consts import (
    HealthOverallStatus,
    InstanceHealthStatus,
    ServiceExpectedStatusAlias,
    ServiceRuntimeStatus,
)
from cancan_microstack.public.schemas.infra.enums import ServiceType
from cancan_microstack.public.schemas.infra.overview import ServiceOverview
from cancan_microstack.public.schemas.infra.service_registry import ServiceInstance
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.service_info_op import get_all_service_info
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.service_registry import (
    get_all_service_names,
    get_all_services,
    get_service_by_instance,
    get_service_instances as db_get_service_instances,
)
from linglong_web import LinglongConfig
from linglong_web.utils import logger


class ServiceRegistryDomain:
    """
    服务注册查询域
    Service Registry Query Domain

    职责：直接查询并返回由 infrasrv 清理和维护的服务注册数据。
    Responsibility: Directly query and return service registry data maintained and cleaned by infrasrv.
    """

    @staticmethod
    def _normalize_service_name(service_name: str) -> str:
        """规范化服务名（兼容 .service 后缀）
        Normalize service name (compatible with .service suffix)
        """
        value = (service_name or "").strip()
        if value.endswith(".service"):
            return value[:-len(".service")]
        return value

    @staticmethod
    def _normalize_expected_status(expected_status: str) -> ServiceRuntimeStatus:
        """规范化期望状态
        Normalize expected status string
        """
        value = (expected_status or ServiceRuntimeStatus.RUNNING.value).strip().lower()
        if value in {
            ServiceExpectedStatusAlias.STOP.value,
            ServiceExpectedStatusAlias.STOPPED.value,
            ServiceExpectedStatusAlias.DOWN.value,
        }:
            return ServiceRuntimeStatus.STOPPED
        return ServiceRuntimeStatus.RUNNING

    @staticmethod
    def _extract_instance_timestamp(instance: ServiceInstance) -> datetime | None:
        """提取实例最近活动时间
        Extract last seen timestamp for an instance
        """
        for field_name in ("last_heartbeat", "update_time", "created_time"):
            timestamp = getattr(instance, field_name, None)
            if timestamp is not None:
                if timestamp.tzinfo is None:
                    return timestamp.replace(tzinfo=timezone.utc)
                return timestamp
        return None

    def _is_stale_instance(self, instance: ServiceInstance, now: datetime) -> bool:
        """判断实例是否超时陈旧
        Determine whether an instance is stale by heartbeat/update timestamp
        """
        stale_seconds = int(getattr(LinglongConfig, "SERVICE_INSTANCE_STALE_SECONDS", 180) or 180)
        if stale_seconds <= 0:
            return False

        last_seen = self._extract_instance_timestamp(instance)
        if last_seen is None:
            return False

        return (now - last_seen).total_seconds() > stale_seconds

    def _build_instance_dedupe_key(self, instance: ServiceInstance) -> str:
        """构建实例去重键
        Build dedupe key for instance consolidation
        """
        normalized_service_name = self._normalize_service_name(instance.service_name)

        if instance.container_name:
            return f"{normalized_service_name}|container:{instance.container_name}"

        return (
            f"{normalized_service_name}|endpoint:{instance.host}:{instance.port}:{instance.internal_port}"
        )

    async def _load_expected_status_map(self) -> Dict[str, ServiceRuntimeStatus]:
        """加载服务期望状态映射
        Load expected status map from service info table
        """
        service_info_list = await get_all_service_info()
        status_map: Dict[str, ServiceRuntimeStatus] = {}
        for service_info in service_info_list:
            normalized_service_name = self._normalize_service_name(service_info.service_name)
            status_map[normalized_service_name] = self._normalize_expected_status(service_info.expected_status)
        return status_map

    def _filter_and_dedupe_instances(
            self,
            instances: List[ServiceInstance],
            expected_status_map: Dict[str, ServiceRuntimeStatus],
    ) -> List[ServiceInstance]:
        """过滤陈旧实例并做同容器去重
        Filter stale instances and dedupe duplicated container rows
        """
        now = datetime.now(timezone.utc)
        deduped_instances: Dict[str, ServiceInstance] = {}

        for instance in instances:
            normalized_service_name = self._normalize_service_name(instance.service_name)
            expected_status = expected_status_map.get(normalized_service_name)
            if expected_status == ServiceRuntimeStatus.STOPPED:
                continue

            if self._is_stale_instance(instance, now):
                continue

            dedupe_key = self._build_instance_dedupe_key(instance)
            existing = deduped_instances.get(dedupe_key)
            if existing is None:
                deduped_instances[dedupe_key] = instance
                continue

            existing_ts = self._extract_instance_timestamp(existing)
            current_ts = self._extract_instance_timestamp(instance)
            if existing_ts is None and current_ts is not None:
                deduped_instances[dedupe_key] = instance
            elif existing_ts is not None and current_ts is not None and current_ts >= existing_ts:
                deduped_instances[dedupe_key] = instance

        return list(deduped_instances.values())

    @staticmethod
    def _derive_actual_status(total_instances: int, healthy_instances: int) -> ServiceRuntimeStatus:
        """根据实例统计推导实际状态
        Derive actual status from instance counters
        """
        if total_instances <= 0:
            return ServiceRuntimeStatus.STOPPED
        if healthy_instances > 0:
            return ServiceRuntimeStatus.RUNNING
        return ServiceRuntimeStatus.DEGRADED

    def _to_models(self, instances: List[ServiceInstance]) -> List[ServiceInstance]:
        """将数据库模型转换为 Pydantic 模型 / Convert DB models to Pydantic models."""
        return [ServiceInstance.model_validate(inst, from_attributes=True) for inst in instances]

    async def get_service_instances(self, service_name: str | None = None, only_healthy: bool = True) -> List[ServiceInstance]:
        """
        获取服务实例列表
        Get the list of instances for a service.

        Args:
            service_name: 服务名称 / Service name
            only_healthy: 是否只返回健康实例 / Whether to return only healthy instances
        """
        logger.debug(f"Querying instances for service: {service_name}, only_healthy: {only_healthy}")

        normalized_service_name = self._normalize_service_name(service_name or "")
        health_status_filter = InstanceHealthStatus.HEALTHY if only_healthy else None

        if normalized_service_name:
            instances = await db_get_service_instances(
                normalized_service_name,
                health_status=health_status_filter,
            )
        else:
            instances = await get_all_services()
            if health_status_filter:
                instances = [instance for instance in instances if instance.health_status == health_status_filter]

        expected_status_map = await self._load_expected_status_map()
        cleaned_instances = self._filter_and_dedupe_instances(instances, expected_status_map)
        logger.info(
            "Found %s cleaned instances for service=%s (only_healthy=%s)",
            len(cleaned_instances),
            normalized_service_name or "ALL",
            only_healthy,
        )
        return self._to_models(cleaned_instances)

    async def get_all_instances(self) -> List[ServiceInstance]:
        """
        获取所有服务实例
        Get all service instances.
        """
        logger.debug("Querying all service instances.")
        instances = await get_all_services()
        expected_status_map = await self._load_expected_status_map()
        cleaned_instances = self._filter_and_dedupe_instances(instances, expected_status_map)
        return self._to_models(cleaned_instances)

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """
        获取指定服务实例
        Get a specific service instance.
        """
        instance = await get_service_by_instance(service_name, instance_id)
        return ServiceInstance.model_validate(instance, from_attributes=True) if instance else None

    async def get_all_service_names(self) -> List[str]:
        """
        获取所有服务名称
        Get all service names.
        """
        return await get_all_service_names()

    async def get_services_overview(self) -> List[ServiceOverview]:
        """
        获取所有服务的概览信息（服务名、状态统计）
        基于 service_info_tbl 的元数据配合实例信息完成统计
        包含没有实例运行的服务
        Get an overview of all services (name, status statistics).
        This is based on metadata from service_info_tbl combined with instance information.
        Includes services that have no running instances.
        """
        all_service_info = await get_all_service_info()
        all_instances = await get_all_services()
        service_map: Dict[str, ServiceOverview] = {}
        expected_status_map = await self._load_expected_status_map()
        cleaned_instances = self._filter_and_dedupe_instances(all_instances, expected_status_map)

        for service_info in all_service_info:
            service_name = service_info.service_name
            expected_status = self._normalize_expected_status(service_info.expected_status)
            service_map[service_name] = ServiceOverview(
                service_name=service_name,
                description=service_info.description or "",
                service_type=service_info.service_type or ServiceType.BUSINESS,
                expected_status=expected_status,
                desired_replicas=int(service_info.desired_replicas or 1),
                actual_replicas=int(service_info.actual_replicas or 0),
            )

        for instance in cleaned_instances:
            service_name = self._normalize_service_name(instance.service_name)
            if service_name not in service_map:
                service_map[service_name] = ServiceOverview(
                    service_name=service_name,
                    service_type=ServiceType.BUSINESS,
                    expected_status=ServiceRuntimeStatus.RUNNING,
                )

            service_map[service_name].total_instances += 1
            if instance.status == HealthOverallStatus.UP or instance.status == InstanceHealthStatus.HEALTHY:
                service_map[service_name].healthy_instances += 1
            else:
                service_map[service_name].unhealthy_instances += 1

        for info in service_map.values():
            info.actual_replicas = info.total_instances
            info.actual_status = self._derive_actual_status(info.total_instances, info.healthy_instances)
            info.status_matches_expected = info.expected_status == info.actual_status

            if info.expected_status == ServiceRuntimeStatus.STOPPED:
                if info.actual_status == ServiceRuntimeStatus.STOPPED:
                    info.overall_status = HealthOverallStatus.UP
                else:
                    info.overall_status = HealthOverallStatus.PARTIAL
            elif info.total_instances == 0:
                info.overall_status = HealthOverallStatus.DOWN
            elif info.healthy_instances == 0:
                info.overall_status = HealthOverallStatus.DOWN
            elif info.unhealthy_instances > 0:
                info.overall_status = HealthOverallStatus.PARTIAL
            else:
                info.overall_status = HealthOverallStatus.UP

        logger.info(f"Retrieved overview for {len(service_map)} services")
        return list(service_map.values())

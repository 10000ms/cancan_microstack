"""
服务注册查询应用层
为ops前端提供服务实例查询功能
"""
from typing import (
    List,
)

from cancan_microstack.public.schemas.infra.service_registry import ServiceInstance
from cancan_microstack.public.schemas.infra.overview import ServiceOverview
from cancan_microstack.services.opsbffsrv.domain.service_registry.service_registry import ServiceRegistryDomain


class ServiceRegistryApp:
    def __init__(self):
        self.service_registry_domain = ServiceRegistryDomain()

    async def get_service_instances(self, service_name: str | None = None, only_healthy: bool = True) -> List[ServiceInstance]:
        """获取服务实例列表"""
        return await self.service_registry_domain.get_service_instances(service_name, only_healthy)

    async def get_all_instances(self) -> List[ServiceInstance]:
        """获取所有服务实例"""
        return await self.service_registry_domain.get_all_instances()

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """获取指定服务实例"""
        return await self.service_registry_domain.get_instance(service_name, instance_id)

    async def get_all_service_names(self) -> List[str]:
        """获取所有服务名称"""
        return await self.service_registry_domain.get_all_service_names()

    async def get_services_overview(self) -> List[ServiceOverview]:
        """获取所有服务的概览信息"""
        return await self.service_registry_domain.get_services_overview()

from typing import (
    List,
    Dict,
    Any,
    Optional,
)

from cancan_microstack.public.schemas.infra.service_registry import (
    ServiceRegistryCreate,
    ServiceInstance,
)
from cancan_microstack.services.infrasrv.domain.registry.service_registry import ServiceRegistry


class ServiceRegistryApp:
    def __init__(self):
        self.service_registry_domain = ServiceRegistry()

    async def register_service(self, service: ServiceRegistryCreate) -> None:
        """注册服务"""
        await self.service_registry_domain.register(service)

    async def deregister_service(self, service_name: str, instance_id: str) -> None:
        """注销服务"""
        await self.service_registry_domain.deregister(service_name, instance_id)

    async def get_service_instances(self, service_name: str, only_healthy: bool = True) -> List[ServiceInstance]:
        """获取服务实例列表"""
        return await self.service_registry_domain.get_instances(service_name, only_healthy)

    async def get_all_instances(self) -> List[ServiceInstance]:
        """获取所有服务实例"""
        return await self.service_registry_domain.get_all_instances()

    async def get_instance(self, service_name: str, instance_id: str) -> Optional[ServiceInstance]:
        """获取指定服务实例"""
        return await self.service_registry_domain.get_instance(service_name, instance_id)

    async def push_config_to_service(self, service_name: str) -> Dict[str, Any]:
        """向服务推送配置"""
        return await self.service_registry_domain.push_config_to_service(service_name)

    async def get_all_service_names(self) -> List[str]:
        """获取所有服务名称"""
        return await self.service_registry_domain.get_all_service_names()

    async def get_services_overview(self) -> List[Dict[str, Any]]:
        """获取所有服务的概览信息"""
        return await self.service_registry_domain.get_services_overview()

    async def cleanup_dead_instances(self) -> Dict[str, Any]:
        """清理已经下线的服务实例"""
        return await self.service_registry_domain.cleanup_dead_instances()

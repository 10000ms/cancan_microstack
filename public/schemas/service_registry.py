from typing import Optional

from pydantic import BaseModel


class InstanceMetadata(BaseModel):
    """
    服务实例的元数据
    Metadata for a service instance.
    """
    container_hostname: Optional[str] = None
    network_alias: str
    register_host_source: str
    app_host_binding: str


class ServiceMetadata(BaseModel):
    """
    服务的元数据
    Metadata for a service.
    """
    version: str
    environment: str


class ServiceRegistryPayload(BaseModel):
    """
    向 infrasrv 注册服务时发送的 payload
    Payload sent to infrasrv when registering a service.
    """
    service_name: str
    instance_id: str
    host: str
    port: int
    internal_port: int
    health_check_url: str
    container_name: str
    compose_service_name: str
    service_metadata: ServiceMetadata
    instance_metadata: InstanceMetadata

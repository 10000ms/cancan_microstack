from typing import (
    Optional,
    Dict,
    Any,
    List,
)
from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from cancan_microstack.public.schemas.infra.enums import ServiceType
from cancan_microstack.public.schemas.infra.service_instance import (
    ServiceInstance,
    ServiceInstanceCreate,
)


class ServiceMetadata(BaseModel):
    """服务级元数据 / Service-level metadata record"""

    service_name: str = Field(..., description="服务名称 / Service name")
    description: Optional[str] = Field(default=None, description="服务描述 / Service description")
    service_type: ServiceType = Field(default=ServiceType.BUSINESS, description="服务类型 / Service category")
    owner: Optional[str] = Field(default=None, description="负责人 / Service owner")
    health_check_path: str = Field(default="/internal/health", description="默认健康检查路径 / Default health path")
    deploy_region: Optional[str] = Field(default=None, description="部署区域 / Deployment region")
    config_version: Optional[str] = Field(default=None, description="配置版本 / Config version")
    service_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="服务元数据 / Additional metadata bag (stores owner/region/config/labels)",
    )
    expected_status: str = Field(default="running", description="期望状态 / Expected status")
    desired_replicas: int = Field(default=1, ge=1, description="期望实例数 / Desired replicas")
    actual_replicas: int = Field(default=0, ge=0, description="实际实例数 / Actual replicas")
    last_scale_at: Optional[datetime] = Field(default=None, description="最后扩缩容时间 / Last scale timestamp")
    scale_policy: Dict[str, Any] = Field(default_factory=dict, description="扩缩容策略 / Scale policy")
    registered_time: Optional[datetime] = Field(default=None)
    last_registered_time: Optional[datetime] = Field(default=None)
    created_time: Optional[datetime] = Field(default=None)
    update_time: Optional[datetime] = Field(default=None)

    @model_validator(mode="after")
    def _sync_metadata_fields(self) -> "ServiceMetadata":
        """确保 owner 等字段与 service_metadata 同步 / Keep metadata bag hydrated."""

        metadata = dict(self.service_metadata or {})
        for key, value in (
                ("owner", self.owner),
                ("deploy_region", self.deploy_region),
                ("config_version", self.config_version),
        ):
            if value is None and metadata.get(key) is not None:
                setattr(self, key, metadata.get(key))
            elif value is not None:
                metadata[key] = value

        self.service_metadata = metadata
        return self


class ServiceRegistryCreate(BaseModel):
    """服务注册请求（包含服务级和实例级数据）"""

    service_name: str = Field(..., description="服务名称 / Service name")
    instance_id: str = Field(..., description="实例ID / Instance identifier")
    host: str = Field(..., description="宿主机地址 / Host address")
    port: int = Field(..., description="服务端口 / Service port")
    health_check_url: Optional[str] = Field(default=None, description="实例健康检查 URL / Instance health URL")
    service_metadata: Dict[str, Any] = Field(default_factory=dict, description="服务自定义元数据 / Service metadata")
    instance_metadata: Dict[str, Any] = Field(default_factory=dict, description="实例自定义元数据 / Instance metadata")
    description: Optional[str] = Field(default=None, description="服务描述 / Service description")
    service_type: ServiceType = Field(default=ServiceType.BUSINESS, description="服务类型 / Service type")
    owner: Optional[str] = Field(default=None, description="负责人 / Owner")
    desired_replicas: Optional[int] = Field(default=1, ge=1, description="期望实例数 / Desired replicas")
    expected_status: str = Field(default="running", description="期望状态 / Expected status")
    health_check_path: Optional[str] = Field(default="/internal/health",
                                             description="默认健康检查路径 / Default health path")
    deploy_region: Optional[str] = Field(default=None, description="部署区域 / Deploy region")
    config_version: Optional[str] = Field(default=None, description="配置版本 / Config version")
    scale_policy: Dict[str, Any] = Field(default_factory=dict, description="扩缩容策略 / Scale policy")
    container_name: Optional[str] = Field(default=None, description="容器名称 / Container name")
    compose_service_name: Optional[str] = Field(default=None, description="Compose 服务名 / Compose service")
    internal_port: int = Field(default=8080, description="容器内部端口 / Internal port")

    @model_validator(mode="after")
    def _merge_instance_metadata(self) -> "ServiceRegistryCreate":
        """确保实例元数据包含服务侧透出的信息 / Merge metadata gracefully."""

        if not self.instance_metadata and self.service_metadata:
            self.instance_metadata = dict(self.service_metadata)
        return self

    def to_service_metadata(self) -> ServiceMetadata:
        """转换为服务级元数据 / Convert to service metadata record."""

        metadata_bag = dict(self.service_metadata or {})
        for key, value in (
                ("owner", self.owner),
                ("deploy_region", self.deploy_region),
                ("config_version", self.config_version),
        ):
            if value is not None:
                metadata_bag[key] = value

        return ServiceMetadata(
            service_name=self.service_name,
            description=self.description,
            service_type=self.service_type,
            owner=self.owner,
            desired_replicas=self.desired_replicas or 1,
            expected_status=self.expected_status,
            health_check_path=self.health_check_path or "/internal/health",
            deploy_region=self.deploy_region,
            config_version=self.config_version,
            service_metadata=metadata_bag,
            scale_policy=self.scale_policy,
        )

    def to_instance_payload(self) -> ServiceInstanceCreate:
        """转换为实例创建请求 / Convert into instance creation payload."""

        return ServiceInstanceCreate(
            service_name=self.service_name,
            instance_id=self.instance_id,
            container_name=self.container_name,
            compose_service_name=self.compose_service_name,
            host=self.host,
            port=self.port,
            internal_port=self.internal_port,
            health_check_url=self.health_check_url,
            instance_metadata=self.instance_metadata,
        )


class ServiceMetadataUpdate(BaseModel):
    """服务元数据更新"""

    service_name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    desired_replicas: Optional[int] = Field(default=None, ge=1)
    actual_replicas: Optional[int] = Field(default=None, ge=0)
    expected_status: Optional[str] = None
    health_check_path: Optional[str] = None
    deploy_region: Optional[str] = None
    config_version: Optional[str] = None
    service_metadata: Optional[Dict[str, Any]] = None
    scale_policy: Optional[Dict[str, Any]] = None


class ServiceInstanceList(BaseModel):
    """服务实例列表 / Wrapper around service instances"""

    instances: List[ServiceInstance]

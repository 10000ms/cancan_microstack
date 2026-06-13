"""
服务实例相关的 Pydantic 类型定义
"""
from typing import (
    Optional,
    Dict,
    Any,
)
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ServiceInstance(BaseModel):
    """
    服务实例
    
    表示一个服务实例的完整信息，包括网络配置、健康状态、生命周期等。
    """
    id: Optional[int] = None
    service_name: str = Field(..., description="服务名称")
    instance_id: str = Field(..., description="实例ID")
    container_name: Optional[str] = Field(default=None, description="Docker容器名 / Docker container name")
    compose_service_name: Optional[str] = Field(default=None, description="Docker Compose服务名 / Compose service name")
    host: str = Field(..., description="宿主机地址")
    port: int = Field(..., description="服务端口")
    internal_port: int = Field(default=8080, description="容器内部端口")
    status: str = Field(..., description="实例状态 (UP|DOWN|UNHEALTHY) / Instance status")
    expected_status: str = Field(default="UP", description="期望状态 (UP|DOWN) / Desired status")
    health_check_url: Optional[str] = Field(default=None, description="健康检查URL / Health check URL")
    health_status: Optional[str] = Field(None, description="健康状态: healthy|unhealthy|unknown")
    last_health_check: Optional[datetime] = Field(None, description="最后健康检查时间")
    last_heartbeat: Optional[datetime] = Field(None, description="最后心跳时间")
    consecutive_failures: int = Field(default=0, description="连续失败次数")
    last_health_error: Optional[str] = Field(None, description="最后健康检查错误")
    started_at: Optional[datetime] = Field(None, description="启动时间")
    stopped_at: Optional[datetime] = Field(None, description="停止时间")
    restart_count: int = Field(default=0, description="重启次数")
    cpu_limit: Optional[str] = Field(None, description="CPU限制")
    memory_limit: Optional[str] = Field(None, description="内存限制")
    instance_metadata: Dict[str, Any] = Field(default_factory=dict, description="实例元数据 / Instance metadata")
    flag: int = Field(default=0)
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceInstanceCreate(BaseModel):
    """创建服务实例的请求模型"""
    service_name: str
    instance_id: str
    container_name: Optional[str] = None
    compose_service_name: Optional[str] = None
    host: str
    port: int
    internal_port: int = 8080
    status: str = "UP"
    expected_status: str = "UP"
    health_check_url: Optional[str] = None
    health_status: str = "unknown"
    instance_metadata: Dict[str, Any] = Field(default_factory=dict, description="实例元数据")


class ServiceInstanceUpdate(BaseModel):
    """更新服务实例的请求模型"""
    status: Optional[str] = None
    expected_status: Optional[str] = None
    health_status: Optional[str] = None
    health_check_url: Optional[str] = None
    last_health_check: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: Optional[int] = None
    last_health_error: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    restart_count: Optional[int] = None
    instance_metadata: Optional[Dict[str, Any]] = None


class ServiceInstanceQuery(BaseModel):
    """查询服务实例的请求模型"""
    service_name: Optional[str] = None
    instance_id: Optional[str] = None
    status: Optional[str] = None
    expected_status: Optional[str] = None
    health_status: Optional[str] = None
    limit: int = Field(default=100, le=1000, description="返回结果数量限制")
    offset: int = Field(default=0, description="分页偏移量")

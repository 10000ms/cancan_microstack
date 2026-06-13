"""
服务信息相关的 Pydantic 类型定义
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


class ServiceInfo(BaseModel):
    """服务信息数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    service_name: str = Field(..., description="服务名称")
    description: Optional[str] = Field(default=None, description="服务描述")
    service_type: str = Field(default="business", description="服务类型")
    health_check_path: str = Field(default="/internal/health", description="默认健康检查路径")
    service_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="服务附加元数据（聚合 owner/deploy_region/config_version/labels 等信息）",
    )
    expected_status: str = Field(default="running", description="期望状态: running|stopped")
    # 注意：以下副本数/扩缩容相关字段仅作"记录期望状态"用途，系统不会据此真正增减容器（扩缩容执行未实现）。
    desired_replicas: int = Field(default=1, description="期望副本数（仅记录，不触发扩缩容）")
    actual_replicas: int = Field(default=0, description="实际副本数（由上游上报回填）")
    last_scale_at: Optional[datetime] = Field(default=None, description="最后记录副本数变更的时间（非真实扩缩容动作）")
    scale_policy: Dict[str, Any] = Field(default_factory=dict, description="扩缩容策略（占位，未实现自动扩缩容）")
    registered_time: Optional[datetime] = Field(default=None, description="首次注册时间")
    last_registered_time: Optional[datetime] = Field(default=None, description="最近注册时间")
    flag: int = Field(default=0, description="标志位")
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



class ServiceInfoCreate(BaseModel):
    """创建服务信息的请求模型"""

    service_name: str = Field(..., description="服务名称", min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, description="服务描述")
    service_type: str = Field(default="business", description="服务类型：infrastructure, business, ops")
    health_check_path: str = Field(default="/internal/health", description="健康检查路径")
    service_metadata: Dict[str, Any] = Field(default_factory=dict, description="服务附加元数据")
    desired_replicas: int = Field(default=1, ge=1, description="期望副本数")
    actual_replicas: int = Field(default=0, ge=0, description="当前副本数")
    expected_status: str = Field(default="running", description="期望状态")
    scale_policy: Dict[str, Any] = Field(default_factory=dict, description="扩缩容策略")


class ServiceInfoUpdate(BaseModel):
    """更新服务信息的请求模型"""
    description: Optional[str] = Field(default=None, description="服务描述")
    service_type: Optional[str] = Field(default=None, description="服务类型")
    health_check_path: Optional[str] = Field(default=None, description="健康检查路径")
    service_metadata: Optional[Dict[str, Any]] = Field(default=None, description="服务附加元数据")
    expected_status: Optional[str] = Field(default=None, description="期望状态")
    desired_replicas: Optional[int] = Field(default=None, ge=1, description="期望副本数")
    actual_replicas: Optional[int] = Field(default=None, ge=0, description="当前副本数")
    scale_policy: Optional[Dict[str, Any]] = Field(default=None, description="扩缩容策略")

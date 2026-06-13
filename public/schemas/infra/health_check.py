from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.health_consts import InstanceHealthStatus


class InstanceHealthDetail(BaseModel):
    """单个实例的健康检查详情模型"""
    instance_id: str = Field(..., description="实例ID")
    service_name: str = Field(..., description="服务名称")
    host: str = Field(..., description="主机")
    port: int = Field(..., description="端口")
    status: str = Field(..., description="实例运行状态")
    health_status: InstanceHealthStatus = Field(
        InstanceHealthStatus.UNKNOWN, description="健康状态"
    )
    consecutive_failures: int = Field(0, description="连续失败次数")
    exempted: bool = Field(False, description="是否被豁免")
    exemption_reason: Optional[str] = Field(None, description="豁免原因")
    expected_stopped: bool = Field(False, description="是否期望停止")
    action_taken: Optional[str] = Field(None, description="采取的自动动作标识")
    # 使用 Optional[str] 接受 ISO 字符串或 datetime，方便与现有代码兼容
    last_heartbeat: Optional[str] = Field(None, description="最后心跳时间 (ISO string)")


class HealthCheckSummary(BaseModel):
    """整体健康检查汇总结果模型"""
    total: int = Field(..., description="实例总数")
    healthy: int = Field(default=0, description="健康实例数")
    unhealthy: int = Field(default=0, description="不健康实例数")
    degraded: int = Field(default=0, description="降级实例数")
    exempted: int = Field(default=0, description="豁免实例数")
    expected_stopped: int = Field(default=0, description="期望停止实例数")
    details: List[InstanceHealthDetail] = Field(default_factory=list, description="实例详情列表")


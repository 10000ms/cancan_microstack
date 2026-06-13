from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)


class PushDetail(BaseModel):
    """
    配置推送单实例结果模型
    Result model for a single push-to-service attempt
    """
    instance_id: str = Field(..., description="Instance ID")
    host: str = Field(..., description="Host")
    port: int = Field(..., description="Port")
    status: str = Field(..., description="Result status, see OperationStatus")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class PushResult(BaseModel):
    """
    配置推送汇总结果模型
    Summary model for push-to-service operations
    """
    service_name: str = Field(..., description="Service name")
    total_instances: int = Field(..., description="Total target instances")
    success: int = Field(default=0, description="Successful pushes")
    failed: int = Field(default=0, description="Failed pushes")
    details: List[PushDetail] = Field(default_factory=list, description="Per-instance push details")

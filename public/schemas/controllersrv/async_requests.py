"""
controllersrv 异步 API 请求模型
"""
from typing import (
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.operation_consts import (
    InitiatedBy,
    InitiatedFrom,
)


class AsyncOperationParams(BaseModel):
    """异步操作参数"""
    instance_id: Optional[str] = Field(default=None, description="实例ID")
    reason: str = Field(..., description="操作原因")


class AsyncServiceOperationPayload(BaseModel):
    """异步服务操作请求体"""
    service_name: str = Field(..., description="服务名称, e.g., 'infrasrv.service'")
    operation_params: AsyncOperationParams = Field(..., description="操作参数")
    initiated_by: InitiatedBy = Field(..., description="操作发起者")
    initiated_from: InitiatedFrom = Field(..., description="发起来源")

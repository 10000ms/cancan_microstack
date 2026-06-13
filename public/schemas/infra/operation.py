"""
异步操作相关的 Pydantic 模型

供 opsbffsrv 和 infrasrv 之间通信使用
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

from cancan_microstack.public.const.operation_consts import (
    OperationType,
    OperationStatus,
    InitiatedBy,
    InitiatedFrom,
)


class OperationCreateRequest(BaseModel):
    """创建操作记录请求"""
    operation_id: str = Field(..., description="操作ID")
    operation_type: OperationType = Field(..., description="操作类型")
    service_name: str = Field(..., description="服务名称（带 .service 后缀）")
    operation_params: Dict[str, Any] = Field(default_factory=dict, description="操作参数")
    status: OperationStatus = Field(default=OperationStatus.PENDING, description="操作状态")
    initiated_by: InitiatedBy = Field(default=InitiatedBy.OPSBFFSRV, description="操作发起者")
    initiated_from: InitiatedFrom = Field(default=InitiatedFrom.FRONTEND, description="发起来源")


class OperationUpdateRequest(BaseModel):
    """更新操作记录请求"""
    operation_id: str = Field(..., description="操作ID")
    status: Optional[OperationStatus] = Field(default=None, description="操作状态")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    result: Optional[Dict[str, Any]] = Field(default=None, description="操作结果")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class OperationQueryRequest(BaseModel):
    """查询操作记录请求"""
    operation_id: Optional[str] = Field(default=None, description="操作ID")
    service_name: Optional[str] = Field(default=None, description="服务名称")
    status: Optional[OperationStatus] = Field(default=None, description="操作状态")
    limit: int = Field(default=50, ge=1, le=1000, description="返回记录数")
    offset: int = Field(default=0, ge=0, description="偏移量")


class Operation(BaseModel):
    """操作记录"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    operation_id: str
    operation_type: str  # 保持字符串以兼容数据库
    service_name: str
    operation_params: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # 保持字符串以兼容数据库
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    last_retry_at: Optional[datetime] = None
    initiated_by: str = "system"  # 保持字符串以兼容数据库
    initiated_from: str = "unknown"  # 保持字符串以兼容数据库
    flag: int = 0
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



class OperationResponse(BaseModel):
    """操作响应"""
    operation: Optional[Operation] = None


class OperationListResponse(BaseModel):
    """操作列表响应"""
    operations: list[Operation] = Field(default_factory=list)
    count: int = 0

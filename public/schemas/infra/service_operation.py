"""
服务操作相关的 Pydantic 类型定义
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
    OperationStatus,
)


class ServiceOperation(BaseModel):
    """
    服务操作记录
    
    表示一个服务操作的完整信息，包括操作状态、执行时间、结果等。
    """
    id: Optional[int] = None
    operation_id: str = Field(..., description="唯一操作ID")
    operation_type: str = Field(..., description="操作类型: start|stop|restart|scale")
    service_name: str = Field(..., description="服务名称")
    operation_params: Dict[str, Any] = Field(default_factory=dict, description="操作参数")
    status: str = Field(..., description="操作状态: pending|running|success|failed|timeout")
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    result: Dict[str, Any] = Field(default_factory=dict, description="执行结果详情")
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(default=0, description="已重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    last_retry_at: Optional[datetime] = Field(None, description="最后重试时间")
    initiated_by: Optional[str] = Field(None, description="操作发起者")
    initiated_from: Optional[str] = Field(None, description="发起来源")
    flag: int = Field(default=0)
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceOperationCreate(BaseModel):
    """创建服务操作的请求模型"""
    operation_id: str
    operation_type: str
    service_name: str
    operation_params: Dict[str, Any] = Field(default_factory=dict)
    status: str = OperationStatus.PENDING
    initiated_by: Optional[str] = None
    initiated_from: Optional[str] = None
    max_retries: int = 3


class ServiceOperationUpdate(BaseModel):
    """更新服务操作的请求模型"""
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    last_retry_at: Optional[datetime] = None


class ServiceOperationQuery(BaseModel):
    """查询服务操作的请求模型"""
    operation_id: Optional[str] = None
    service_name: Optional[str] = None
    operation_type: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=10, le=100, description="返回结果数量限制")
    offset: int = Field(default=0, description="分页偏移量")

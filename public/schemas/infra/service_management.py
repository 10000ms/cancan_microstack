"""
服务管理相关的 Pydantic 模型 / Service Management Related Pydantic Models

供 infrasrv 和 opsbffsrv 之间通信使用 / Used for communication between infrasrv and opsbffsrv
"""
from typing import (
    Dict,
    Any,
    Optional,
)
from datetime import datetime
from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.operation_consts import (
    OperationType,
    OperationStatus,
    InitiatedBy,
    InitiatedFrom,
)


class ServiceManagementRequest(BaseModel):
    """
    服务管理请求模型 / Service Management Request Model
    
    统一的服务管理请求格式，适用于所有操作类型（start/stop/restart）
    Unified service management request format for supported operation types
    """
    operation_id: str = Field(..., description="操作ID，用于跟踪操作生命周期 / Operation ID for tracking lifecycle")
    service_name: str = Field(..., description="服务名称（带 .service 后缀）/ Service name (with .service suffix)")
    operation_type: OperationType = Field(..., description="操作类型 / Operation type")
    operation_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="操作参数（按需使用）/ Operation parameters (optional)"
    )
    initiated_by: InitiatedBy = Field(
        default=InitiatedBy.OPSBFFSRV,
        description="操作发起者 / Operation initiator"
    )
    initiated_from: InitiatedFrom = Field(
        default=InitiatedFrom.FRONTEND,
        description="发起来源 / Initiation source"
    )


class ServiceManagementResponse(BaseModel):
    """
    服务管理响应模型 / Service Management Response Model
    
    包含操作执行结果和当前状态 / Contains operation execution result and current status
    """
    operation_id: str = Field(..., description="操作ID / Operation ID")
    status: OperationStatus = Field(..., description="操作状态 / Operation status")
    service_name: str = Field(..., description="服务名称 / Service name")
    message: str = Field(default="", description="响应消息 / Response message")
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="操作结果详情（可选）/ Operation result details (optional)"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="错误信息（如果操作失败）/ Error message (if operation failed)"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="操作开始时间 / Operation start time"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="操作完成时间 / Operation completion time"
    )


class ServiceOperationResult(BaseModel):
    """
    服务操作结果模型（用于 controllersrv 返回）/ Service Operation Result Model (for controllersrv response)
    
    解析 controllersrv 返回的详细操作结果 / Parse detailed operation results from controllersrv
    """
    success: bool = Field(..., description="操作是否成功 / Whether operation succeeded")
    message: str = Field(default="", description="结果消息 / Result message")
    service_names: list[str] = Field(default_factory=list, description="涉及的服务列表 / List of involved services")
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="详细信息（容器状态、日志等）/ Detailed info (container status, logs, etc.)"
    )


class ServiceManagementStats(BaseModel):
    """
    服务管理统计信息 / Service Management Statistics
    
    用于监控和分析服务管理操作的性能和结果 / Used for monitoring and analyzing service management performance
    """
    total_operations: int = Field(default=0, description="总操作数 / Total operations")
    success_count: int = Field(default=0, description="成功次数 / Success count")
    failed_count: int = Field(default=0, description="失败次数 / Failed count")


class HookResult(BaseModel):
    """
    钩子执行结果模型 / Hook Execution Result Model
    
    用于预操作钩子返回结果 / Used for pre-operation hook return results
    """
    allow: bool = Field(default=True, description="是否允许操作继续 / Whether to allow operation to continue")
    reason: str = Field(default="", description="拒绝原因（如果 allow=False）/ Rejection reason (if allow=False)")


class ControllerSrvResult(BaseModel):
    """
    ControllerSrv 调用结果模型 / ControllerSrv Call Result Model
    
    统一 controllersrv 返回的结果格式 / Unified result format from controllersrv
    """
    success: bool = Field(..., description="操作是否成功 / Whether operation succeeded")
    message: str = Field(default="", description="结果消息 / Result message")
    error: Optional[str] = Field(default=None, description="错误信息 / Error message")
    retry_count: Optional[int] = Field(default=None, description="重试次数 / Retry count")
    pending_count: int = Field(default=0, description="待处理次数 / Pending count")
    avg_duration_seconds: float = Field(default=0.0, description="平均耗时（秒）/ Average duration (seconds)")


class ServiceManagementAPIResponse(BaseModel):
    """
    服务管理 API 响应 DTO / Service Management API Response DTO
    
    用于 API 层返回给客户端的响应格式 / Used for API layer to return response to client
    """
    operation_id: str = Field(..., description="操作ID / Operation ID")
    status: str = Field(..., description="操作状态 / Operation status")
    service_name: str = Field(..., description="服务名称 / Service name")
    message: str = Field(default="", description="响应消息 / Response message")
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="操作结果详情（可选）/ Operation result details (optional)"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="错误信息（如果操作失败）/ Error message (if operation failed)"
    )
    started_at: Optional[str] = Field(
        default=None,
        description="操作开始时间（ISO格式）/ Operation start time (ISO format)"
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="操作完成时间（ISO格式）/ Operation completion time (ISO format)"
    )

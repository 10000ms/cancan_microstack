"""
controllersrv API 响应模型

定义了 controllersrv API 的标准响应模型，以确保一致性和类型安全。
"""
from typing import (
    Dict,
    Any,
    Optional,
    List,
)
from enum import Enum
from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.operation_consts import (
    OperationStatus,
)


class ApiResponseKey(str, Enum):
    """API 响应字典的 Key"""
    SUCCESS = "success"
    STATUS = "status"
    SERIAL_NUMBER = "serial_number"
    OPERATION = "operation"
    SERVICE_NAMES = "service_names"
    MESSAGE = "message"
    TASK = "task"
    TASKS = "tasks"
    COUNT = "count"
    STATS = "stats"


class EnqueueSuccessResponse(BaseModel):
    """任务入队成功响应"""
    success: bool = Field(default=True, description="是否成功")
    status: str = Field(default=OperationStatus.PENDING, description="任务状态")
    serial_number: str = Field(..., description="流水号")
    operation: str = Field(..., description="操作类型")
    service_names: List[str] = Field(..., description="服务名称列表")
    message: str = Field(default="Task enqueued successfully", description="响应消息")


class EnqueueErrorResponse(BaseModel):
    """任务入队失败响应"""
    success: bool = Field(default=False, description="是否成功")
    status: str = Field(default="error", description="任务状态")
    serial_number: Optional[str] = Field(None, description="流水号")
    message: str = Field(..., description="错误消息")


class TaskNotFoundResponse(BaseModel):
    """任务未找到响应"""
    success: bool = Field(False, description="是否成功")
    message: str = Field(..., description="响应消息")


class TaskStatusResponse(BaseModel):
    """任务状态查询成功响应"""
    success: bool = Field(default=True, description="是否成功")
    task: Dict[str, Any] = Field(..., description="任务详情")


class TaskListResponse(BaseModel):
    """任务列表响应"""
    success: bool = Field(default=True, description="是否成功")
    tasks: List[Dict[str, Any]] = Field(..., description="任务列表")
    count: int = Field(..., description="任务数量")


class TaskQueueStats(BaseModel):
    """任务队列统计信息"""
    queue_size: int = Field(..., description="当前队列中的任务数")
    total_tasks: int = Field(..., description="历史总任务数（包括已完成）")
    active_serial_numbers: int = Field(..., description="活跃流水号数量")
    status_counts: Dict[str, int] = Field(..., description="按状态统计的任务数量")
    max_queue_size: int = Field(..., description="队列最大容量")


class QueueStatsResponse(BaseModel):
    """队列统计信息响应"""
    success: bool = Field(default=True, description="是否成功")
    stats: TaskQueueStats = Field(..., description="统计信息")
    error: Optional[str] = Field(default=None, description="错误信息")


class ServiceStatusResponse(BaseModel):
    """服务状态响应"""
    success: bool = Field(..., description="是否成功")
    services: List[str] = Field(default_factory=list, description="服务列表")
    error: Optional[str] = Field(default=None, description="错误信息")


class ServiceListResponse(BaseModel):
    """服务列表响应"""
    success: bool = Field(..., description="是否成功")
    services: List[str] = Field(default_factory=list, description="服务列表")
    error: Optional[str] = Field(default=None, description="错误信息")


class ContainerHealthResponse(BaseModel):
    """容器健康状态响应"""
    success: bool = Field(..., description="是否成功")
    service_name: Optional[str] = Field(default=None, description="服务名称")
    containers: List[Dict[str, Any]] = Field(default_factory=list, description="容器健康详情列表")
    error: Optional[str] = Field(default=None, description="错误信息")


class ComposeStatusResponse(BaseModel):
    """Docker Compose 状态响应"""
    success: bool = Field(..., description="是否成功")
    is_running: bool = Field(default=False, description="是否运行中")
    service_count: Optional[int] = Field(default=None, description="服务数量")
    services: List[str] = Field(default_factory=list, description="服务列表")
    error: Optional[str] = Field(default=None, description="错误信息")


class ComposeStatusRequest(BaseModel):
    """Compose 状态查询请求（预留扩展）"""
    # 当前 get_compose_status() 不需要参数，此模型预留供未来使用
    pass
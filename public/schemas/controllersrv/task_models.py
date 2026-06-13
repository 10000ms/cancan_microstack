"""
任务领域模型

定义Task相关的领域模型类
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
)


class Task(BaseModel):
    """
    任务数据类
    
    Attributes:
        serial_number: 流水号（唯一标识）
        operation: 操作类型
        service_names: 服务名称列表
        params: 其他参数
        status: 任务状态
        created_at: 创建时间
        started_at: 开始执行时间
        finished_at: 完成时间
        result: 执行结果
        error: 错误信息
        retry_count: 重试次数
    """
    serial_number: str
    operation: OperationType
    service_names: list
    params: Dict[str, Any] = Field(default_factory=dict)
    status: OperationStatus = OperationStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump(mode='json')

    def mark_running(self):
        """标记为运行中"""
        self.status = OperationStatus.RUNNING
        self.started_at = datetime.now()

    def mark_success(self, result: Dict[str, Any]):
        """标记为成功"""
        self.status = OperationStatus.SUCCESS
        self.finished_at = datetime.now()
        self.result = result

    def mark_failed(self, error: str):
        """标记为失败"""
        self.status = OperationStatus.FAILED
        self.finished_at = datetime.now()
        self.error = error

    def mark_timeout(self):
        """标记为超时"""
        self.status = OperationStatus.TIMEOUT
        self.finished_at = datetime.now()
        self.error = "Task execution timeout"

    def mark_cancelled(self):
        """标记为已取消"""
        self.status = OperationStatus.CANCELLED
        self.finished_at = datetime.now()
        self.error = "Task cancelled"

    def is_finished(self) -> bool:
        """是否已完成（无论成功还是失败）"""
        return self.status in {
            OperationStatus.SUCCESS,
            OperationStatus.FAILED,
            OperationStatus.TIMEOUT,
            OperationStatus.CANCELLED,
        }

    def execution_time(self) -> Optional[float]:
        """计算执行时间（秒）"""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        elif self.started_at:
            # 正在执行中
            return (datetime.now() - self.started_at).total_seconds()
        return None

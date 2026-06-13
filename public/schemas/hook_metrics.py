"""
钩子指标相关的 Pydantic 模型
Hook metrics related Pydantic models
"""
from typing import (
    Dict,
    List,
)
from datetime import datetime
from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.metrics_enums import MetricType


class Metric(BaseModel):
    """指标数据类"""
    name: str = Field(description="指标名称")
    metric_type: MetricType = Field(description="指标类型")
    description: str = Field(default="", description="指标描述")
    value: float = Field(default=0.0, description="指标值")
    labels: Dict[str, str] = Field(default_factory=dict, description="标签")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class MetricValue(BaseModel):
    """指标值 / Metric value"""
    value: float = Field(description="指标值 / Metric value")
    labels: Dict[str, str] = Field(default_factory=dict, description="标签 / Labels")
    timestamp: datetime = Field(description="时间戳 / Timestamp")


class MetricData(BaseModel):
    """指标数据 / Metric data"""
    name: str = Field(description="指标名称 / Metric name")
    type: str = Field(description="指标类型 / Metric type")
    description: str = Field(description="指标描述 / Metric description")
    values: List[MetricValue] = Field(default_factory=list, description="指标值列表 / Metric values")


class HookExecutionHistoryItem(BaseModel):
    """钩子执行历史项 / Hook execution history item"""
    hook_name: str = Field(description="钩子名称 / Hook name")
    result: str = Field(description="执行结果 / Execution result")
    message: str = Field(description="消息 / Message")
    execution_time: float = Field(description="执行时间(秒) / Execution time (seconds)")
    has_modified_service_info: bool = Field(description="是否修改了服务信息 / Whether service info was modified")


class HookInfo(BaseModel):
    """钩子信息 / Hook information"""
    name: str = Field(description="钩子名称 / Hook name")
    priority: str = Field(description="优先级 / Priority")
    type: str = Field(description="钩子类型 / Hook type")


class HooksByPriority(BaseModel):
    """按优先级分组的钩子 / Hooks grouped by priority"""
    CRITICAL: List[HookInfo] = Field(default_factory=list, description="关键优先级钩子 / Critical priority hooks")
    HIGH: List[HookInfo] = Field(default_factory=list, description="高优先级钩子 / High priority hooks")
    MEDIUM: List[HookInfo] = Field(default_factory=list, description="中优先级钩子 / Medium priority hooks")
    LOW: List[HookInfo] = Field(default_factory=list, description="低优先级钩子 / Low priority hooks")


class HookTypeStatus(BaseModel):
    """钩子类型状态 / Hook type status"""
    count: int = Field(description="钩子数量 / Hook count")
    hooks_by_priority: HooksByPriority = Field(description="按优先级分组的钩子 / Hooks by priority")


class MetricSummary(BaseModel):
    """指标摘要 / Metric summary"""
    type: str = Field(description="指标类型 / Metric type")
    description: str = Field(description="指标描述 / Metric description")
    latest_value: float = Field(description="最新值 / Latest value")
    latest_timestamp: datetime = Field(description="最新时间戳 / Latest timestamp")


class HookPerformance(BaseModel):
    """钩子性能统计 / Hook performance statistics"""
    total_executions: int = Field(default=0, description="总执行次数 / Total executions")
    successful_executions: int = Field(default=0, description="成功执行次数 / Successful executions")
    failed_executions: int = Field(default=0, description="失败执行次数 / Failed executions")
    total_execution_time: float = Field(default=0.0, description="总执行时间 / Total execution time")
    min_execution_time: float = Field(default=float('inf'), description="最小执行时间 / Min execution time")
    max_execution_time: float = Field(default=0.0, description="最大执行时间 / Max execution time")
    avg_execution_time: float = Field(default=0.0, description="平均执行时间 / Average execution time")


class OverallPerformanceStats(BaseModel):
    """整体性能统计 / Overall performance statistics"""
    total_executions: int = Field(description="总执行次数 / Total executions")
    successful_executions: int = Field(description="成功执行次数 / Successful executions")
    failed_executions: int = Field(description="失败执行次数 / Failed executions")
    success_rate: float = Field(description="成功率(%) / Success rate (%)")


class BaseMetricLabels(BaseModel):
    """指标标签基类"""
    hook_name: str
    hook_type: str


class HookExecutionLabels(BaseMetricLabels):
    """hook_executions_total 指标的标签"""
    result: str


class HookFailureLabels(BaseMetricLabels):
    """hook_failures_total 指标的标签"""
    error_type: str


class ActiveHooksLabels(BaseModel):
    """active_hooks 指标的标签"""
    hook_type: str


class HookRejectionLabels(BaseModel):
    """hook_rejections_total 指标的标签"""
    hook_name: str
    reason: str

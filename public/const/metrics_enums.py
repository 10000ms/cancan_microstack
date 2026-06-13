"""
Metrics-related enums.
"""
from enum import StrEnum


class MetricType(StrEnum):
    """指标类型枚举"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class HookMetricName(StrEnum):
    """钩子指标名称枚举"""
    EXECUTIONS_TOTAL = "hook_executions_total"
    EXECUTION_DURATION_SECONDS = "hook_execution_duration_seconds"
    FAILURES_TOTAL = "hook_failures_total"
    ACTIVE_HOOKS = "active_hooks"
    REJECTIONS_TOTAL = "hook_rejections_total"


class HookMetricLabel(StrEnum):
    """钩子指标标签枚举"""
    HOOK_NAME = "hook_name"
    HOOK_TYPE = "hook_type"
    RESULT = "result"
    ERROR_TYPE = "error_type"
    REASON = "reason"


class HookMetricResult(StrEnum):
    """钩子指标结果枚举"""
    SUCCESS = "success"
    FAILURE = "failure"

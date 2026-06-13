"""
钩子监控指标模块

提供钩子执行相关的指标收集和暴露功能
"""
import threading
from datetime import (
    datetime,
    timezone,
)
from typing import (
    Dict,
    List,
    Optional,
    Union,
    Callable,
)

from cancan_microstack.public.const.metrics_enums import (
    MetricType,
    HookMetricName,
    HookMetricResult,
)
from cancan_microstack.public.schemas.hook_metrics import (
    HookExecutionLabels,
    HookFailureLabels,
    ActiveHooksLabels,
    HookRejectionLabels,
    Metric,
)
from linglong_web.utils import logger

# 类型别名，用于表示所有可能的标签模型
LabelModel = Union[HookExecutionLabels, HookFailureLabels, ActiveHooksLabels, HookRejectionLabels]


class HookMetrics:
    """钩子指标收集器"""

    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
        self._init_default_metrics()

    def _init_default_metrics(self):
        """初始化默认指标"""
        self.register_metric(
            HookMetricName.EXECUTIONS_TOTAL,
            MetricType.COUNTER,
            "Total number of hook executions",
        )
        self.register_metric(
            HookMetricName.EXECUTION_DURATION_SECONDS,
            MetricType.HISTOGRAM,
            "Time spent executing hooks",
        )
        self.register_metric(
            HookMetricName.FAILURES_TOTAL,
            MetricType.COUNTER,
            "Total number of hook failures",
        )
        self.register_metric(
            HookMetricName.ACTIVE_HOOKS,
            MetricType.GAUGE,
            "Number of active hooks",
        )
        self.register_metric(
            HookMetricName.REJECTIONS_TOTAL,
            MetricType.COUNTER,
            "Total number of service rejections by hooks",
        )

    def register_metric(self, name: HookMetricName, metric_type: MetricType, description: str) -> None:
        """注册指标"""
        with self._lock:
            self._metrics[name] = Metric(
                name=name,
                metric_type=metric_type,
                description=description,
            )
            logger.debug(f"Registered metric: {name}")

    def _update_metric(self, name: HookMetricName, value: float, labels: Optional[LabelModel],
                       update_func: Callable[[Metric, float], None]) -> None:
        """通用指标更新方法"""
        with self._lock:
            metric_name_str = name
            if metric_name_str not in self._metrics:
                logger.warning(f"Metric {metric_name_str} not registered")
                return

            metric = self._metrics[metric_name_str]
            update_func(metric, value)
            metric.labels = labels.model_dump() if labels else {}
            metric.timestamp = datetime.now(timezone.utc)
            logger.debug(f"Updated metric {metric_name_str} with value {value}")

    def increment_counter(self, name: HookMetricName, value: float = 1.0, labels: Optional[LabelModel] = None) -> None:
        """增加计数器指标"""

        def _increment(metric: Metric, val: float):
            metric.value += val

        self._update_metric(name, value, labels, _increment)

    def set_gauge(self, name: HookMetricName, value: float, labels: Optional[LabelModel] = None) -> None:
        """设置仪表盘指标值"""

        def _set(metric: Metric, val: float):
            metric.value = val

        self._update_metric(name, value, labels, _set)

    def observe_histogram(self, name: HookMetricName, value: float, labels: Optional[LabelModel] = None) -> None:
        """观察直方图指标值"""

        def update_histogram(metric: Metric, new_value: float):
            if metric.value == 0:
                metric.value = new_value
            else:
                metric.value = (metric.value + new_value) / 2  # 简单移动平均

        self._update_metric(name, value, labels, update_histogram)

    def get_metric(self, name: HookMetricName) -> Optional[Metric]:
        """获取指标"""
        with self._lock:
            return self._metrics.get(name)

    def get_all_metrics(self) -> List[Metric]:
        """获取所有指标"""
        with self._lock:
            return list(self._metrics.values())


class HookMetricsCollector:
    """钩子指标收集器 - 用于在钩子执行过程中收集指标"""

    def __init__(self, metrics: HookMetrics):
        self._metrics = metrics

    def record_hook_execution(self, hook_name: str, hook_type: str,
                              success: bool, duration: float,
                              error_type: Optional[str] = None) -> None:
        """记录钩子执行"""
        result = HookMetricResult.SUCCESS if success else HookMetricResult.FAILURE
        execution_labels = HookExecutionLabels(
            hook_name=hook_name,
            hook_type=hook_type,
            result=result
        )
        self._metrics.increment_counter(HookMetricName.EXECUTIONS_TOTAL, labels=execution_labels)

        duration_labels = HookExecutionLabels(hook_name=hook_name, hook_type=hook_type, result=result)
        self._metrics.observe_histogram(
            HookMetricName.EXECUTION_DURATION_SECONDS,
            duration,
            labels=duration_labels
        )

        if not success:
            failure_labels = HookFailureLabels(
                hook_name=hook_name,
                hook_type=hook_type,
                error_type=error_type or "unknown"
            )
            self._metrics.increment_counter(HookMetricName.FAILURES_TOTAL, labels=failure_labels)

    def record_hook_rejection(self, hook_name: str, reason: str) -> None:
        """记录钩子拒绝注册"""
        rejection_labels = HookRejectionLabels(hook_name=hook_name, reason=reason)
        self._metrics.increment_counter(HookMetricName.REJECTIONS_TOTAL, labels=rejection_labels)

    def update_active_hooks_count(self, hook_type: str, count: int) -> None:
        """更新活跃钩子数量"""
        active_hooks_labels = ActiveHooksLabels(hook_type=hook_type)
        self._metrics.set_gauge(HookMetricName.ACTIVE_HOOKS, count, labels=active_hooks_labels)


# 全局指标实例
_global_metrics: Optional[HookMetrics] = None
_global_collector: Optional[HookMetricsCollector] = None


def get_metrics() -> HookMetrics:
    """获取全局指标实例"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = HookMetrics()
    return _global_metrics


def get_metrics_collector() -> HookMetricsCollector:
    """获取全局指标收集器实例"""
    global _global_collector
    if _global_collector is None:
        _global_collector = HookMetricsCollector(get_metrics())
    return _global_collector


def reset_metrics() -> None:
    """重置全局指标"""
    global _global_metrics, _global_collector
    _global_metrics = None
    _global_collector = None

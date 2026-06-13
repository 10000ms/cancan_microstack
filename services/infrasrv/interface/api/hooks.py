"""
钩子监控API接口

提供钩子执行指标、历史记录和状态的查询接口
"""
from datetime import datetime
from typing import Dict

from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.const.hook_enums import HookType
from linglong_web.utils import logger
from cancan_microstack.services.infrasrv.domain.hooks.hook_registry import get_hook_manager
from cancan_microstack.services.infrasrv.domain.hooks.metrics import get_metrics
from cancan_microstack.public.schemas.hook_metrics import (
    MetricData,
    MetricValue,
    HookExecutionHistoryItem,
    HookTypeStatus,
    HooksByPriority,
    HookInfo,
    MetricSummary,
    HookPerformance,
    OverallPerformanceStats,
)


async def get_hook_metrics_handler() -> APIResponse[Dict[str, dict]]:
    """
    获取钩子指标 / Get hook metrics
    
    Returns:
        钩子执行指标 / Hook execution metrics
    """
    metrics = get_metrics()
    all_metrics = metrics.get_all_metrics()

    # 转换为 Pydantic 模型 / Convert to Pydantic models
    metrics_data: Dict[str, MetricData] = {}
    for metric in all_metrics:
        if metric.name not in metrics_data:
            metrics_data[metric.name] = MetricData(
                name=metric.name,
                type=metric.metric_type,
                description=metric.description,
                values=[]
            )

        metrics_data[metric.name].values.append(
            MetricValue(
                value=metric.value,
                labels=metric.labels,
                timestamp=metric.timestamp
            )
        )

    # 转换为字典用于响应 / Convert to dict for response
    result = {name: data.model_dump() for name, data in metrics_data.items()}

    return build_success_response(data=result)


async def get_hook_history_handler(request) -> APIResponse[dict]:
    """
    获取钩子执行历史 / Get hook execution history
    
    Query Parameters:
        hook_name: 钩子名称过滤（可选）/ Hook name filter (optional)
        limit: 返回记录数限制（默认100）/ Limit of records to return (default 100)
    
    Returns:
        钩子执行历史记录 / Hook execution history records
    """
    query_params = request.query_params
    hook_name = query_params.get("hook_name")
    limit = int(query_params.get("limit", 100))

    hook_manager = get_hook_manager()
    history = hook_manager.get_execution_history(
        service_name=None,
        hook_name=hook_name,
        limit=limit
    )

    # 转换为 Pydantic 模型 / Convert to Pydantic models
    history_items = [
        HookExecutionHistoryItem(
            hook_name=result.hook_name,
            result=result.result,
            message=result.message,
            execution_time=result.execution_time,
            has_modified_service_info=False  # 这个字段需要从 result 中获取，如果有的话
        )
        for result in history
    ]

    return build_success_response(
        data={
            "total": len(history_items),
            "history": [item.model_dump() for item in history_items],
        }
    )


async def get_hook_status_handler() -> APIResponse[dict]:
    """
    获取钩子状态 / Get hook status
    
    Returns:
        钩子状态信息 / Hook status information
    """
    hook_manager = get_hook_manager()

    # 获取所有钩子类型 / Get all hook types
    hook_types = [HookType.PRE_REGISTER, HookType.POST_REGISTER, HookType.PRE_DEREGISTER, HookType.POST_DEREGISTER]

    status_data: Dict[str, HookTypeStatus] = {}
    total_hooks = 0

    for hook_type in hook_types:
        hooks = hook_manager.get_hooks(hook_type)
        total_hooks += len(hooks)

        # 按优先级分组 / Group by priority
        hooks_by_priority = HooksByPriority()

        for hook in hooks:
            hook_info = HookInfo(
                name=hook.name,
                priority=hook.priority.name,
                type=hook.__class__.__name__
            )

            # 根据优先级添加到对应列表 / Add to corresponding list by priority
            priority_name = hook.priority.name
            if priority_name == "HIGHEST":
                hooks_by_priority.CRITICAL.append(hook_info)
            elif priority_name == "HIGH":
                hooks_by_priority.HIGH.append(hook_info)
            elif priority_name in ("MEDIUM", "NORMAL"):
                hooks_by_priority.MEDIUM.append(hook_info)
            else:  # LOW, LOWEST
                hooks_by_priority.LOW.append(hook_info)

        status_data[hook_type] = HookTypeStatus(
            count=len(hooks),
            hooks_by_priority=hooks_by_priority
        )

    # 获取指标摘要 / Get metrics summary
    metrics = get_metrics()
    all_metrics = metrics.get_all_metrics()

    metrics_summary: Dict[str, MetricSummary] = {}
    for metric in all_metrics:
        if metric.name not in metrics_summary:
            metrics_summary[metric.name] = MetricSummary(
                type=metric.metric_type,
                description=metric.description,
                latest_value=metric.value,
                latest_timestamp=metric.timestamp
            )

    return build_success_response(
        data={
            "total_hooks": total_hooks,
            "hook_types": {k: v.model_dump() for k, v in status_data.items()},
            "metrics_summary": {k: v.model_dump() for k, v in metrics_summary.items()},
            "timestamp": datetime.now().isoformat(),
        }
    )


async def reset_hook_metrics_handler() -> APIResponse[dict]:
    """
    重置钩子指标 / Reset hook metrics
    
    Returns:
        操作结果 / Operation result
    """
    metrics = get_metrics()
    all_metrics = metrics.get_all_metrics()

    # 重置所有计数器指标 / Reset all counter metrics
    reset_count = 0
    for metric in all_metrics:
        if metric.metric_type.value == "counter":
            metrics.reset_metric(metric.name)
            reset_count += 1

    # 清空钩子执行历史 / Clear hook execution history
    hook_manager = get_hook_manager()
    hook_manager.clear_history()

    logger.info(f"Reset {reset_count} metrics and cleared hook history")

    return build_success_response(
        data={
            "reset_metrics_count": reset_count,
            "history_cleared": True,
        }
    )


async def get_hook_performance_handler(request) -> APIResponse[dict]:
    """
    获取钩子性能统计 / Get hook performance statistics
    
    Query Parameters:
        hook_name: 钩子名称过滤（可选）/ Hook name filter (optional)
        time_range: 时间范围（小时，默认24）/ Time range (hours, default 24)
    
    Returns:
        钩子性能统计 / Hook performance statistics
    """
    query_params = request.query_params
    hook_name = query_params.get("hook_name")
    time_range = int(query_params.get("time_range", 24))

    hook_manager = get_hook_manager()
    history = hook_manager.get_execution_history(
        service_name=None,
        hook_name=hook_name,
        limit=1000  # 获取更多历史记录 / Get more history records
    )

    # 由于 history 中的记录没有时间戳字段，我们直接使用所有记录 / Use all records since history doesn't have timestamp field
    filtered_history = [
        result for result in history
        if result.execution_time > 0
    ]

    if not filtered_history:
        return build_success_response(
            data={
                "message": "No performance data available in the specified time range",
                "time_range_hours": time_range,
            }
        )

    # 按钩子名称分组 / Group by hook name
    performance_by_hook: Dict[str, HookPerformance] = {}
    for result in filtered_history:
        hook_name_key = result.hook_name
        if hook_name_key not in performance_by_hook:
            performance_by_hook[hook_name_key] = HookPerformance()

        perf = performance_by_hook[hook_name_key]
        perf.total_executions += 1
        perf.total_execution_time += result.execution_time

        if result.result.value == "success":
            perf.successful_executions += 1
        else:
            perf.failed_executions += 1

        if result.execution_time < perf.min_execution_time:
            perf.min_execution_time = result.execution_time

        if result.execution_time > perf.max_execution_time:
            perf.max_execution_time = result.execution_time

        # 计算平均执行时间 / Calculate average execution time
        perf.avg_execution_time = perf.total_execution_time / perf.total_executions

    # 计算总体统计 / Calculate overall statistics
    total_executions = sum(perf.total_executions for perf in performance_by_hook.values())
    total_successful = sum(perf.successful_executions for perf in performance_by_hook.values())
    total_failed = sum(perf.failed_executions for perf in performance_by_hook.values())

    overall_stats = OverallPerformanceStats(
        total_executions=total_executions,
        successful_executions=total_successful,
        failed_executions=total_failed,
        success_rate=(total_successful / total_executions * 100) if total_executions > 0 else 0
    )

    return build_success_response(
        data={
            "time_range_hours": time_range,
            "overall_stats": overall_stats.model_dump(),
            "performance_by_hook": {k: v.model_dump() for k, v in performance_by_hook.items()},
        }
    )

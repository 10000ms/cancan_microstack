"""
Caddy 访问日志 API 接口

提供日志查询、安全事件监控、异常分析等功能
"""
from typing import (
    Optional,
)

from linglong_web.utils import logger
from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import build_success_response
from linglong_web import limiter
from cancan_microstack.public.schemas.caddy import AccessLogQuery
from cancan_microstack.services.opsbffsrv.application.caddy.access_log_analysis_app import AccessLogAnalysisApp

# 应用层实例
_log_app = AccessLogAnalysisApp()


@limiter("30/second")
async def search_logs_handler(query: AccessLogQuery) -> APIResponse[dict]:
    """
    搜索访问日志
    
    Args:
        query: 查询条件
    
    Returns:
        统一响应格式
    """
    logger.info(f"搜索访问日志: service={query.service_name}, route_id={query.route_id}")
    logs = await _log_app.search_logs(query)

    return build_success_response(data={
        "logs": [log.model_dump() for log in logs],
        "total": len(logs),
        "query": query.model_dump(),
    })


@limiter("20/second")
async def get_security_events_handler(
        event_type: str = "waf_blocked",
        limit: int = 100,
) -> APIResponse[dict]:
    """
    获取安全事件（WAF 拦截、限流触发）

    Args:
        event_type: 事件类型（waf_blocked / rate_limited）
        limit: 返回数量

    Returns:
        统一响应格式
    """
    logger.info(f"获取安全事件: type={event_type}, limit={limit}")
    # 应用层返回 dict 信封：{status, event_type, count, data:[CaddyAccessLog...]}
    # 直接透传该信封，APIResponse 会自动序列化其中的 pydantic 模型。
    result = await _log_app.get_security_events(event_type=event_type, limit=limit)

    return build_success_response(data=result)


@limiter("20/second")
async def analyze_geographic_distribution_handler(
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[dict]:
    """
    分析地理分布

    Args:
        start_time: 开始时间（ISO 8601格式）
        end_time: 结束时间（ISO 8601格式）

    Returns:
        统一响应格式
    """
    logger.info("分析地理分布")
    # 应用层返回 dict 信封：{status, data:[...]}，直接透传。
    result = await _log_app.analyze_geographic_distribution(
        start_time=start_time,
        end_time=end_time
    )

    return build_success_response(data=result)


@limiter("20/second")
async def analyze_status_code_distribution_handler(
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[dict]:
    """
    分析状态码分布

    Args:
        start_time: 开始时间（ISO 8601格式）
        end_time: 结束时间（ISO 8601格式）

    Returns:
        统一响应格式
    """
    logger.info("分析状态码分布")
    # 应用层返回 dict 信封：{status, data:[...]}，直接透传。
    result = await _log_app.analyze_status_code_distribution(
        start_time=start_time,
        end_time=end_time
    )

    return build_success_response(data=result)


@limiter("10/second")
async def detect_suspicious_ips_handler(
        threshold: int = 1000,
        time_window_minutes: int = 10,
) -> APIResponse[dict]:
    """
    检测可疑 IP（高频访问）
    
    Args:
        threshold: 阈值（次数）
        time_window_minutes: 时间窗口（分钟）
    
    Returns:
        统一响应格式
    """
    logger.info(f"检测可疑IP: threshold={threshold}, window={time_window_minutes}min")
    # 对齐应用层签名：detect_suspicious_ips(time_window, request_threshold)
    # 应用层返回 dict 信封：{status, count, data:[SuspiciousIP...]}，直接透传。
    result = await _log_app.detect_suspicious_ips(
        time_window=time_window_minutes,
        request_threshold=threshold,
    )

    return build_success_response(data=result)


@limiter("20/second")
async def analyze_error_patterns_handler(hours: int = 24) -> APIResponse[dict]:
    """
    分析错误模式（4xx/5xx）

    Args:
        hours: 分析过去多少小时的错误（默认 24 小时）

    Returns:
        统一响应格式
    """
    logger.info(f"分析错误模式: hours={hours}")
    # 对齐应用层签名：analyze_error_patterns(hours)
    # 应用层返回 dict 信封：{status, total_errors, error_rate, ...}，直接透传。
    result = await _log_app.analyze_error_patterns(hours=hours)

    return build_success_response(data=result)


@limiter("5/second")
async def cleanup_old_logs_handler(days: int = 30) -> APIResponse[dict | None]:
    """
    清理旧日志
    
    Args:
        days: 保留天数（默认30天）
    
    Returns:
        统一响应格式
    """
    logger.info(f"清理旧日志: days={days}")
    result = await _log_app.cleanup_old_logs(days)

    return build_success_response(data=result)

"""
Caddy 统计分析 API 接口

提供实时统计、趋势分析、Top 排行等功能
Provides realtime statistics, trend analysis, and top rankings for Caddy traffic
"""
from typing import (
    List,
    Optional,
)
import http

from linglong_web.utils import logger
from cancan_microstack.public.const.opsbffsrv_error import OpsbffsrvCaddyStatsErrorCode
from cancan_microstack.public.schemas.caddy import (
    CaddyStats,
    RealtimeStatsResponse,
    GlobalTrendResponse,
    ServiceTrendResponse,
    RouteTrendResponse,
    TopDimensionResponse,
    CleanupStatsResponse,
)
from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import build_success_response
from linglong_web import limiter
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.application.caddy.stats_aggregation_app import StatsAggregationApp

# 应用层实例 / Application layer instance
_stats_app = StatsAggregationApp()


def _check_result_or_raise(
        result: Optional[dict],
        error_code: OpsbffsrvCaddyStatsErrorCode,
        default_message: str,
) -> dict:
    """验证应用层返回的结果字典，失败则抛出异常"""

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
            error_code=error_code,
            msg=default_message
        )

    if result.get("status") != "success":
        message = result.get("error") or default_message
        raise HTTPException(
            status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
            error_code=error_code,
            msg=message
        )

    return result


def _normalize_stats_sequence(raw_items: List[object]) -> List[CaddyStats]:
    """将原始数据转换为 CaddyStats 列表
    Normalize raw stats payload into a list of CaddyStats models
    """

    normalized: List[CaddyStats] = []
    for item in raw_items:
        if isinstance(item, CaddyStats):
            normalized.append(item)
        else:
            normalized.append(CaddyStats.model_validate(item))
    return normalized


@limiter("30/second")
async def get_realtime_global_stats_handler() -> APIResponse[RealtimeStatsResponse]:
    """获取实时全局统计 / Fetch realtime global statistics"""

    logger.info("获取实时全局统计")
    stats = await _stats_app.get_realtime_global_stats()
    payload = RealtimeStatsResponse(stats=stats)
    return build_success_response(data=payload)


@limiter("30/second")
async def get_realtime_service_stats_handler(service_name: str) -> APIResponse[RealtimeStatsResponse]:
    """获取实时服务统计 / Fetch realtime statistics for specific service"""

    logger.info("获取实时服务统计: service=%s", service_name)
    stats = await _stats_app.get_realtime_service_stats(service_name)
    if stats:
        payload = RealtimeStatsResponse(stats=stats)
        return build_success_response(data=payload)

    raise HTTPException(
        status_code=http.HTTPStatus.NOT_FOUND.value,
        error_code=OpsbffsrvCaddyStatsErrorCode.REALTIME_SERVICE_NOT_FOUND,
        msg="服务统计不存在"
    )


@limiter("20/second")
async def get_global_trend_handler(
        period: str = "hourly",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[GlobalTrendResponse]:
    """获取全局趋势数据 / Fetch global traffic trend"""

    logger.info("获取全局趋势: period=%s", period)
    raw_result = await _stats_app.get_global_trend(period, start_time, end_time)
    result = _check_result_or_raise(
        raw_result,
        OpsbffsrvCaddyStatsErrorCode.GLOBAL_TREND_FAILED,
        "获取全局趋势失败",
    )

    trend_items = _normalize_stats_sequence(result.get("data", [])) if result else []
    payload = GlobalTrendResponse(
        period=result.get("period", period),
        hours=result.get("hours", 0),
        trend=trend_items,
    )
    return build_success_response(data=payload)


@limiter("20/second")
async def get_service_trend_handler(
        service_name: str,
        period: str = "hourly",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[ServiceTrendResponse]:
    """获取服务趋势数据 / Fetch service-specific trend"""

    logger.info("获取服务趋势: service=%s, period=%s", service_name, period)
    raw_result = await _stats_app.get_service_trend(service_name, period, start_time, end_time)
    result = _check_result_or_raise(
        raw_result,
        OpsbffsrvCaddyStatsErrorCode.SERVICE_TREND_FAILED,
        "获取服务趋势失败",
    )

    trend_items = _normalize_stats_sequence(result.get("data", [])) if result else []
    payload = ServiceTrendResponse(
        service_name=result.get("service", service_name),
        period=result.get("period", period),
        hours=result.get("hours", 0),
        trend=trend_items,
    )
    return build_success_response(data=payload)


@limiter("20/second")
async def get_route_trend_handler(
        route_id: int,
        period: str = "hourly",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[RouteTrendResponse]:
    """获取路由趋势数据 / Fetch route-specific trend"""

    logger.info("获取路由趋势: route_id=%s, period=%s", route_id, period)
    raw_result = await _stats_app.get_route_trend(route_id, period, start_time, end_time)
    result = _check_result_or_raise(
        raw_result,
        OpsbffsrvCaddyStatsErrorCode.ROUTE_TREND_FAILED,
        "获取路由趋势失败",
    )

    trend_items = _normalize_stats_sequence(result.get("data", [])) if result else []
    payload = RouteTrendResponse(
        route_id=route_id,
        period=result.get("period", period),
        hours=result.get("hours", 0),
        trend=trend_items,
    )
    return build_success_response(data=payload)


@limiter("20/second")
async def get_top_countries_handler(
        limit: int = 10,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[TopDimensionResponse]:
    """获取访问量 Top 国家 / Fetch top countries by traffic volume"""

    logger.info("获取Top国家: limit=%s", limit)
    raw_result = await _stats_app.get_top_countries(limit, start_time, end_time)
    result = _check_result_or_raise(
        raw_result,
        OpsbffsrvCaddyStatsErrorCode.TOP_COUNTRY_FAILED,
        "获取Top国家失败",
    )

    items = _normalize_stats_sequence(result.get("data", [])) if result else []
    payload = TopDimensionResponse(
        period=result.get("period", "hour"),
        limit=limit,
        items=items,
    )
    return build_success_response(data=payload)


@limiter("20/second")
async def get_top_ips_handler(
        limit: int = 10,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
) -> APIResponse[TopDimensionResponse]:
    """获取访问量 Top IP / Fetch top IPs by request volume"""

    logger.info("获取Top IP: limit=%s", limit)
    raw_result = await _stats_app.get_top_ips(limit, start_time, end_time)
    result = _check_result_or_raise(
        raw_result,
        OpsbffsrvCaddyStatsErrorCode.TOP_IP_FAILED,
        "获取Top IP失败",
    )

    items = _normalize_stats_sequence(result.get("data", [])) if result else []
    payload = TopDimensionResponse(
        period=result.get("period", "hour"),
        limit=limit,
        items=items,
    )
    return build_success_response(data=payload)


@limiter("5/second")
async def cleanup_old_stats_handler(days: int = 90) -> APIResponse[CleanupStatsResponse]:
    """清理旧统计数据 / Cleanup outdated statistics records"""

    logger.info("清理旧统计数据: days=%s", days)
    raw_result = await _stats_app.cleanup_old_stats(days)
    result = _check_result_or_raise(
        raw_result,
        OpsbffsrvCaddyStatsErrorCode.CLEANUP_FAILED,
        "清理旧统计数据失败",
    )

    message = result.get("message", "清理完成") if result else "清理完成"
    payload = CleanupStatsResponse(message=message)
    return build_success_response(data=payload)

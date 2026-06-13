"""
Caddy 路由管理 API 接口

提供路由的 CRUD 操作、同步、统计等功能
"""
from typing import (
    Any,
    Dict,
    Optional,
)
import http

from linglong_web.utils import logger
from linglong_web import limiter
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.caddy.route import (
    ToggleRoutePayload,
)
from linglong_web import (
    build_success_response,
)
from cancan_microstack.public.schemas.caddy import CaddyRouteCreate, CaddyRouteUpdate
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.application.caddy.route_management_app import RouteManagementApp

# 应用层实例
_route_app = RouteManagementApp()


@limiter("20/second")
async def create_route_handler(route_data: CaddyRouteCreate) -> APIResponse[Dict[str, Any]]:
    """
    创建新路由
    
    Args:
        route_data: 路由创建数据
    
    Returns:
        统一响应格式
    """
    logger.info(f"创建路由: domain={route_data.domain}, path={route_data.path_pattern}")
    result = await _route_app.create_route_and_sync(route_data)

    if result.get("status") == "success":
        return build_success_response(data=result)

    raise HTTPException(
        status_code=http.HTTPStatus.BAD_REQUEST.value,
        msg=result.get("message") or result.get("error") or "创建路由失败",
        detail=str(result)
    )


@limiter("20/second")
async def update_route_handler(route_id: int, route_data: CaddyRouteUpdate) -> APIResponse[Dict[str, Any]]:
    """
    更新路由
    
    Args:
        route_id: 路由ID
        route_data: 更新数据
    
    Returns:
        统一响应格式
    """
    logger.info(f"更新路由: id={route_id}")
    update_payload = route_data.model_dump(exclude_unset=True)
    # 确保包含有效更新字段，避免空请求 / Ensure payload carries real updates and reject empty requests
    if not update_payload:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg="更新内容不能为空",
        )

    result = await _route_app.update_route_and_sync(route_id, update_payload)

    if result.get("status") == "success":
        return build_success_response(data=result)

    raise HTTPException(
        status_code=http.HTTPStatus.BAD_REQUEST.value,
        msg=result.get("message") or result.get("error") or "更新路由失败",
        detail=str(result)
    )


@limiter("20/second")
async def get_route_handler(route_id: int) -> APIResponse[Dict[str, Any]]:
    """
    获取单个路由详情
    
    Args:
        route_id: 路由ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"获取路由: id={route_id}")
    route = await _route_app.get_route(route_id)

    if route:
        return build_success_response(data=route.model_dump())

    raise HTTPException(
        status_code=http.HTTPStatus.NOT_FOUND.value,
        msg="路由不存在"
    )


@limiter("20/second")
async def list_routes_handler(
        domain: Optional[str] = None,
        service_name: Optional[str] = None,
        is_enabled: Optional[bool] = None
) -> APIResponse[Dict[str, Any]]:
    """
    列出路由（支持过滤）
    
    Args:
        domain: 域名过滤
        service_name: 服务名称过滤
        is_enabled: 启用状态过滤
    
    Returns:
        统一响应格式
    """
    logger.info(f"列出路由: domain={domain}, service={service_name}, enabled={is_enabled}")

    # 构建过滤条件
    filters = {}
    if domain:
        filters['domain'] = domain
    if service_name:
        filters['upstream_service'] = service_name
    if is_enabled is not None:
        filters['is_enabled'] = is_enabled

    routes = await _route_app.list_all_routes(filters=filters if filters else None)

    return build_success_response(data={
        "routes": [r.model_dump() for r in routes],
        "total": len(routes)
    })


@limiter("10/second")
async def delete_route_handler(route_id: int) -> APIResponse[Dict[str, Any]]:
    """
    删除路由
    
    Args:
        route_id: 路由ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"删除路由: id={route_id}")
    result = await _route_app.delete_route_and_sync(route_id)

    if result.get("status") == "success":
        return build_success_response(data=result)

    raise HTTPException(
        status_code=http.HTTPStatus.BAD_REQUEST.value,
        msg=result.get("message") or result.get("error") or "删除路由失败",
        detail=str(result)
    )


@limiter("10/second")
async def toggle_route_handler(route_id: int, payload: Optional[ToggleRoutePayload] = None) -> APIResponse[
    Dict[str, Any]]:
    """
    切换路由启用状态
    
    Args:
        route_id: 路由ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"切换路由状态: id={route_id}")
    target_enabled = payload.enabled if payload else None
    # 支持指定目标状态，默认自动取反 / Allow explicit target state while auto-inverting when absent
    result = await _route_app.toggle_route_and_sync(route_id, target_enabled)

    if result.get("status") == "success":
        return build_success_response(data=result)

    raise HTTPException(
        status_code=http.HTTPStatus.BAD_REQUEST.value,
        msg=result.get("message") or result.get("error") or "切换路由状态失败",
        detail=str(result)
    )


@limiter("5/second")
async def sync_all_routes_handler() -> APIResponse[Dict[str, Any]]:
    """
    同步所有路由到 Caddy
    
    Returns:
        统一响应格式
    """
    logger.info("同步所有路由到 Caddy")
    result = await _route_app.sync_all_routes()

    if result.get("status") == "success":
        return build_success_response(data=result)

    raise HTTPException(
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        msg=result.get("message", "同步路由失败"),
        detail=str(result)
    )


@limiter("20/second")
async def get_route_statistics_handler() -> APIResponse[Dict[str, Any]]:
    """
    获取路由统计信息
    
    Returns:
        统一响应格式
    """
    logger.info("获取路由统计信息")
    stats = await _route_app.get_route_statistics()

    return build_success_response(data=stats)


@limiter("20/second")
async def get_routes_by_domain_handler(domain: str) -> APIResponse[Dict[str, Any]]:
    """
    根据域名获取路由列表
    
    Args:
        domain: 域名
    
    Returns:
        统一响应格式
    """
    logger.info(f"根据域名获取路由: domain={domain}")
    routes = await _route_app.get_routes_by_domain(domain)

    return build_success_response(data={
        "domain": domain,
        "routes": [r.model_dump() for r in routes],
        "total": len(routes)
    })

"""
Caddy 限流管理 API 接口

提供限流规则的 CRUD 操作、IP 白黑名单管理、统计等功能
"""
from typing import (
    List,
    Optional,
)
import http

from pydantic import (
    BaseModel,
    Field,
)

from linglong_web.utils import logger
from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import limiter
from cancan_microstack.public.schemas.caddy import CaddyRateLimitCreate, CaddyRateLimitUpdate
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.application.caddy.rate_limit_management_app import RateLimitManagementApp

# 应用层实例
_rate_limit_app = RateLimitManagementApp()


class _IPListPayload(BaseModel):
    """IP 列表请求体
    IP list payload
    """

    ips: List[str] = Field(default_factory=list)


def _extract_error_message(result: dict, default_message: str) -> str:
    """统一提取错误信息
    Extract normalized error message
    """
    return result.get("message") or result.get("error") or default_message


@limiter("20/second")
async def create_rate_limit_handler(rule_data: CaddyRateLimitCreate) -> APIResponse[dict]:
    """
    创建限流规则
    
    Args:
        rule_data: 限流规则数据
    
    Returns:
        统一响应格式
    """
    logger.info(f"创建限流规则: name={rule_data.rule_name}")
    result = await _rate_limit_app.create_rate_limit(rule_data)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "创建限流规则失败"),
            detail=str(result)
        )


@limiter("20/second")
async def update_rate_limit_handler(rule_id: int, rule_data: CaddyRateLimitUpdate) -> APIResponse[dict]:
    """
    更新限流规则
    
    Args:
        rule_id: 规则ID
        rule_data: 更新数据
    
    Returns:
        统一响应格式
    """
    logger.info(f"更新限流规则: id={rule_id}")
    result = await _rate_limit_app.update_rate_limit(rule_id, rule_data)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "更新限流规则失败"),
            detail=str(result)
        )


@limiter("20/second")
async def get_rate_limit_handler(rule_id: int) -> APIResponse[dict]:
    """
    获取单个限流规则
    
    Args:
        rule_id: 规则ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"获取限流规则: id={rule_id}")
    rule = await _rate_limit_app.get_rate_limit(rule_id)

    if rule:
        return build_success_response(data=rule.model_dump())
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.NOT_FOUND.value,
            msg="限流规则不存在"
        )


@limiter("20/second")
async def list_rate_limits_handler(
        match_type: Optional[str] = None,
        is_enabled: Optional[bool] = None
) -> APIResponse[dict]:
    """
    列出限流规则（支持过滤）
    
    Args:
        match_type: 匹配类型（path/header/ip/query）
        is_enabled: 启用状态
    
    Returns:
        统一响应格式
    """
    logger.info(f"列出限流规则: type={match_type}, enabled={is_enabled}")
    rules = await _rate_limit_app.list_rate_limits(
        match_type=match_type,
        is_enabled=is_enabled
    )

    return build_success_response(data={
        "rules": [r.model_dump() for r in rules],
        "total": len(rules)
    })


@limiter("10/second")
async def delete_rate_limit_handler(rule_id: int) -> APIResponse[dict]:
    """
    删除限流规则
    
    Args:
        rule_id: 规则ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"删除限流规则: id={rule_id}")
    result = await _rate_limit_app.delete_rate_limit(rule_id)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "删除限流规则失败"),
            detail=str(result)
        )


@limiter("10/second")
async def toggle_rate_limit_handler(rule_id: int) -> APIResponse[dict]:
    """
    切换限流规则启用状态
    
    Args:
        rule_id: 规则ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"切换限流规则状态: id={rule_id}")
    result = await _rate_limit_app.toggle_rate_limit(rule_id)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "切换限流规则状态失败"),
            detail=str(result)
        )


@limiter("10/second")
async def add_whitelist_ips_handler(rule_id: int, payload: _IPListPayload) -> APIResponse[dict]:
    """
    添加IP白名单
    
    Args:
        rule_id: 规则ID
        ips: IP列表
    
    Returns:
        统一响应格式
    """
    logger.info(f"添加IP白名单: rule_id={rule_id}, count={len(payload.ips)}")
    result = await _rate_limit_app.add_whitelist_ips(rule_id, payload.ips)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "添加IP白名单失败"),
            detail=str(result)
        )


@limiter("10/second")
async def remove_whitelist_ips_handler(rule_id: int, payload: _IPListPayload) -> APIResponse[dict]:
    """
    移除IP白名单
    
    Args:
        rule_id: 规则ID
        ips: IP列表
    
    Returns:
        统一响应格式
    """
    logger.info(f"移除IP白名单: rule_id={rule_id}, count={len(payload.ips)}")
    result = await _rate_limit_app.remove_whitelist_ips(rule_id, payload.ips)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "移除IP白名单失败"),
            detail=str(result)
        )


@limiter("10/second")
async def add_blacklist_ips_handler(rule_id: int, payload: _IPListPayload) -> APIResponse[dict]:
    """
    添加IP黑名单
    
    Args:
        rule_id: 规则ID
        ips: IP列表
    
    Returns:
        统一响应格式
    """
    logger.info(f"添加IP黑名单: rule_id={rule_id}, count={len(payload.ips)}")
    result = await _rate_limit_app.add_blacklist_ips(rule_id, payload.ips)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "添加IP黑名单失败"),
            detail=str(result)
        )


@limiter("10/second")
async def remove_blacklist_ips_handler(rule_id: int, payload: _IPListPayload) -> APIResponse[dict]:
    """
    移除IP黑名单
    
    Args:
        rule_id: 规则ID
        ips: IP列表
    
    Returns:
        统一响应格式
    """
    logger.info(f"移除IP黑名单: rule_id={rule_id}, count={len(payload.ips)}")
    result = await _rate_limit_app.remove_blacklist_ips(rule_id, payload.ips)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=_extract_error_message(result, "移除IP黑名单失败"),
            detail=str(result)
        )


@limiter("20/second")
async def get_rate_limit_statistics_handler() -> APIResponse[dict]:
    """
    获取限流统计信息
    
    Returns:
        统一响应格式
    """
    logger.info("获取限流统计信息")
    stats = await _rate_limit_app.get_rate_limit_statistics()

    return build_success_response(data=stats)

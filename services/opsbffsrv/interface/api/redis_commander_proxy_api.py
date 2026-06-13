"""
redis-commander 代理 API
将前端对 /v1/opsbffsrv/redis_commander/* 的请求转发到 redis-commander.internal:8081
"""
import http
from typing import Optional

from starlette.requests import Request
from starlette.responses import (
    RedirectResponse,
    Response,
)
from linglong_web.utils import logger
from linglong_web import http_client
from linglong_web import LinglongConfig

from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.error import ErrorCode


async def redis_commander_proxy_handler(request: Request) -> Response:
    """
    redis-commander 代理处理器 / Proxy handler for redis-commander

    将所有 /v1/opsbffsrv/redis_commander/* 请求转发到 redis-commander.internal:8081/*
    Forward every /v1/opsbffsrv/redis_commander/* request to redis-commander.internal:8081/*
    """
    original_path = request.url.path
    if original_path.endswith("/redis_commander") and not original_path.endswith("/redis_commander/"):
        redirect_response = _build_proxy_aware_redirect(request)
        if redirect_response:
            return redirect_response

        html_content = (
            "<!DOCTYPE html><html lang=\"zh-CN\"><head>"
            "<meta charset=\"utf-8\" />"
            "<title>Redirecting</title>"
            "<script>(function(){var url=new URL(window.location.href);"
            "if(!url.pathname.endsWith('/')){url.pathname=url.pathname+'/';}"
            "window.location.replace(url.toString());})();</script>"
            "</head><body></body></html>"
        )
        return Response(
            content=html_content,
            status_code=http.HTTPStatus.OK.value,
            media_type="text/html",
        )

    redis_path = original_path.replace("/v1/opsbffsrv/redis_commander", "", 1)
    if not redis_path:
        redis_path = "/"

    base_url = (LinglongConfig.REDIS_COMMANDER_BASE_URL or "").rstrip("/")
    target_url = f"{base_url}{redis_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    logger.debug(f"Proxying {request.method} {original_path} -> {target_url}")

    headers = dict(request.headers)
    headers.pop('host', None)

    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()

    resp = await http_client.fetch(
        method=request.method,
        url=target_url,
        format_type='raw',  # 禁止解析二进制响应 / keep binary payload intact
        headers=headers,
        data=body,
        timeout=30.0,
    )

    if not resp:
        logger.error(f"Failed to proxy request to redis-commander: {target_url}")
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_GATEWAY.value,
            error_code=ErrorCode.NETWORK_ERROR,
            msg="Failed to connect to redis-commander",
        )

    content = await resp.read()
    response_headers = dict(resp.headers)
    response_headers.pop('transfer-encoding', None)
    response_headers.pop('content-encoding', None)

    logger.debug(f"Proxied redis-commander response: {resp.status} {len(content)} bytes")

    return Response(
        content=content,
        status_code=resp.status,
        headers=response_headers,
    )


def _build_proxy_aware_redirect(request: Request) -> Optional[RedirectResponse]:
    """构造考虑代理头的 308 重定向 / Build a proxy-aware 308 redirect"""
    forwarded_uri = request.headers.get("x-original-uri") or request.headers.get("x-forwarded-uri")
    corrected_path: Optional[str] = None

    if forwarded_uri:
        corrected_path = forwarded_uri if forwarded_uri.endswith("/") else f"{forwarded_uri}/"
    else:
        forwarded_prefix = request.headers.get("x-forwarded-prefix")
        if forwarded_prefix:
            trimmed = forwarded_prefix.rstrip("/")
            corrected_path = f"{trimmed}/"

    if not corrected_path:
        return None

    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    port = request.headers.get("x-forwarded-port")

    if not host:
        return None

    netloc = host
    if port and ":" not in host:
        netloc = f"{host}:{port}"

    redirect_target = f"{scheme}://{netloc}{corrected_path}"
    if request.url.query:
        redirect_target = f"{redirect_target}?{request.url.query}"

    logger.debug(f"Redirecting redis-commander request to {redirect_target}")
    return RedirectResponse(
        url=redirect_target,
        status_code=http.HTTPStatus.PERMANENT_REDIRECT.value,
    )

"""
pgweb 代理 API
将前端对 /v1/opsbffsrv/pgweb/* 的请求转发到 pgweb.internal:8081
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


async def pgweb_proxy_handler(request: Request) -> Response:
    """
    pgweb 代理处理器
    
    将所有 /v1/opsbffsrv/pgweb/* 请求转发到 pgweb.internal:8081/*
    保持请求方法、查询参数、请求头和请求体不变
    
    Examples:
        GET  /v1/opsbffsrv/pgweb/         -> GET  http://pgweb.internal:8081/
        GET  /v1/opsbffsrv/pgweb/api/info -> GET  http://pgweb.internal:8081/api/info
        POST /v1/opsbffsrv/pgweb/api/sql  -> POST http://pgweb.internal:8081/api/sql
    """
    # 提取原始路径，缺少尾部 / 时优先重定向
    # Extract original path and normalize trailing slash before proxying
    original_path = request.url.path
    if original_path.endswith("/pgweb") and not original_path.endswith("/pgweb/"):
        redirect_response = _build_proxy_aware_redirect(request)
        if redirect_response:
            return redirect_response

        # 回退为在前端执行跳转，确保任何代理路径都能正确追加 /
        # Fallback: client-side redirect to preserve upstream proxy prefixes
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

    pgweb_path = original_path.replace("/v1/opsbffsrv/pgweb", "", 1)

    # 如果路径为空，默认为根路径
    if not pgweb_path:
        pgweb_path = "/"

    # 构建目标 URL
    base_url = (LinglongConfig.PGWEB_BASE_URL or "").rstrip("/")
    target_url = f"{base_url}{pgweb_path}"

    # 保留查询参数
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    logger.debug(f"Proxying {request.method} {original_path} -> {target_url}")

    # 准备转发的请求头（移除 Host 头）
    headers = dict(request.headers)
    headers.pop('host', None)

    # 读取请求体（如果有）
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()

    # 转发请求到 pgweb
    resp = await http_client.fetch(
        method=request.method,
        url=target_url,
        format_type='raw',  # 禁止文本解析以便透传二进制资源 / disable text decode for binary passthrough
        headers=headers,
        data=body,
        timeout=30.0,  # pgweb 查询可能较慢
    )

    if not resp:
        logger.error(f"Failed to proxy request to pgweb: {target_url}")
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_GATEWAY.value,
            error_code=ErrorCode.NETWORK_ERROR,
            msg="Failed to connect to pgweb"
        )

    # 读取响应内容
    content = await resp.read()

    # 准备返回的响应头（移除某些不应该转发的头）
    response_headers = dict(resp.headers)
    response_headers.pop('transfer-encoding', None)
    response_headers.pop('content-encoding', None)

    logger.debug(f"Proxied response: {resp.status} {len(content)} bytes")

    # 返回代理响应
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

    logger.debug(f"Redirecting to {redirect_target} with proxy-aware headers")
    return RedirectResponse(
        url=redirect_target,
        status_code=http.HTTPStatus.PERMANENT_REDIRECT.value,
    )

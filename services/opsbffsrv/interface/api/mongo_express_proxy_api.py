"""
mongo-express 代理 API / Mongo-express proxy API
将前端对 /v1/opsbffsrv/mongo_express/* 的请求转发到 mongo-express.internal:8081
Forward every /v1/opsbffsrv/mongo_express/* request to mongo-express.internal:8081
"""
import base64
import http
from typing import Optional

from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response

from linglong_web.utils import logger
from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.public.error import HTTPException
from linglong_web import http_client
from linglong_web import LinglongConfig


def _build_proxy_aware_redirect(request: Request) -> Optional[RedirectResponse]:
    """构造考虑代理头的 308 重定向 / Build a proxy-aware 308 redirect"""
    forwarded_uri = request.headers.get("x-original-uri") or request.headers.get("x-forwarded-uri")
    corrected_path: Optional[str] = None

    if forwarded_uri:
        corrected_path = forwarded_uri if forwarded_uri.endswith('/') else f"{forwarded_uri}/"
    else:
        forwarded_prefix = request.headers.get("x-forwarded-prefix")
        if forwarded_prefix:
            trimmed = forwarded_prefix.rstrip('/')
            corrected_path = f"{trimmed}/"

    if not corrected_path:
        return None

    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    port = request.headers.get("x-forwarded-port")

    if not host:
        return None

    netloc = host
    if port and ':' not in host:
        netloc = f"{host}:{port}"

    redirect_target = f"{scheme}://{netloc}{corrected_path}"
    if request.url.query:
        redirect_target = f"{redirect_target}?{request.url.query}"

    logger.debug("Redirecting mongo-express request to %s", redirect_target)
    return RedirectResponse(url=redirect_target, status_code=http.HTTPStatus.PERMANENT_REDIRECT.value)


def _ensure_basic_auth(headers: dict[str, str]) -> None:
    """缺省时注入 Basic Auth / Inject Basic auth header when missing."""
    username = LinglongConfig.MONGO_EXPRESS_USERNAME
    password = LinglongConfig.MONGO_EXPRESS_PASSWORD
    if not username or not password:
        return

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    headers["Authorization"] = f"Basic {token}"


async def mongo_express_proxy_handler(request: Request) -> Response:
    """mongo-express 代理处理器 / Proxy handler for mongo-express"""
    original_path = request.url.path
    if original_path.endswith("/mongo_express") and not original_path.endswith("/mongo_express/"):
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
        return Response(content=html_content, status_code=http.HTTPStatus.OK.value, media_type="text/html")

    # Mongo Express with ME_CONFIG_SITE_BASEURL expects requests at that path
    # Do NOT strip the prefix - send original path to upstream
    proxy_path = original_path or "/"
    base_url = (LinglongConfig.MONGO_EXPRESS_BASE_URL or "").rstrip("/")
    target_url = f"{base_url}{proxy_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    logger.debug("Proxying %s %s -> %s", request.method, original_path, target_url)

    headers = dict(request.headers)
    headers.pop('host', None)

    # 强制覆盖 Authorization 头，防止用户的 Token 传递给上游导致 401
    # Force overwrite Authorization header to prevent client tokens from causing upstream 401s
    headers.pop('authorization', None)
    headers.pop('Authorization', None)
    _ensure_basic_auth(headers)

    logger.debug("Proxying to MongoExpress with headers: %s (Auth present: %s)",
                 {k: v for k, v in headers.items() if k.lower() != 'authorization'},
                 'Authorization' in headers)

    body = None
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()

    try:
        resp = await http_client.fetch(
            method=request.method,
            url=target_url,
            format_type='raw',
            headers=headers,
            data=body,
            timeout=30.0,
            passthrough_errors=True,
        )

        if not resp:
            logger.error("Failed to proxy request to mongo-express: %s", target_url)
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_GATEWAY.value,
                error_code=ErrorCode.NETWORK_ERROR,
                msg="Failed to connect to mongo-express",
            )

        content = await resp.read()
        content = await resp.read()

        # 处理响应头：移除 hop-by-hop 头
        response_headers = {}
        content_type = ""
        for k, v in resp.headers.items():
            k_lower = k.lower()
            if k_lower == 'content-type':
                content_type = v
            if k_lower in ('transfer-encoding', 'content-encoding', 'connection', 'keep-alive', 'content-length'):
                continue
            response_headers[k] = v

        # 针对 HTML 响应进行路径重写 / Rewrite paths in HTML responses
        # Mongo Express 默认使用绝对路径 /public/xxx，需要改写为 /v1/opsbffsrv/mongo_express/public/xxx
        if "text/html" in content_type:
            html_str = content.decode("utf-8", errors="replace")
            # 替换 public 资源路径
            html_str = html_str.replace('href="/public/', 'href="/v1/opsbffsrv/mongo_express/public/')
            html_str = html_str.replace('src="/public/', 'src="/v1/opsbffsrv/mongo_express/public/')
            html_str = html_str.replace('href="public/', 'href="/v1/opsbffsrv/mongo_express/public/')
            html_str = html_str.replace('src="public/', 'src="/v1/opsbffsrv/mongo_express/public/')

            # 替换 base href (如果存在) 或注入新的
            if '<base href="' in html_str:
                html_str = html_str.replace('<base href="/"', '<base href="/v1/opsbffsrv/mongo_express/"')
            else:
                # 在 <head> 后插入 base 标签
                html_str = html_str.replace('<head>', '<head><base href="/v1/opsbffsrv/mongo_express/">', 1)

            content = html_str.encode("utf-8")
            # 更新 Content-Length (虽然 starlette Response 会自动处理，但如果是流式传输可能需要注意，这里是一次性读取)
            response_headers.pop("Content-Length", None)

        logger.debug("Proxied mongo-express response: %s %s bytes", resp.status, len(content))

        return Response(content=content, status_code=resp.status, headers=response_headers)

    except Exception as e:
        logger.error("Error proxying to mongo-express: %s", e, exc_info=True)
        # 如果是已知 HTTP 异常直接抛出
        if isinstance(e, HTTPException):
            raise e
        # 其他异常转换为 502 Bad Gateway
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_GATEWAY.value,
            error_code=ErrorCode.NETWORK_ERROR,
            msg=f"Upstream error: {str(e)}",
        )

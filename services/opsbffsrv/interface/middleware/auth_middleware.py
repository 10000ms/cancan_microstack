"""全局认证中间件 / Global authentication middleware for opsbffsrv."""
from fastapi import Request
from fastapi.responses import JSONResponse

from cancan_microstack.services.opsbffsrv.infrastructure.auth import redis_store

AUTH_WHITELIST = [
    "/v1/opsbffsrv/auth/",  # auth 接口本身
    "/health",               # 健康检查
    "/docs",                 # Swagger
    "/openapi.json",         # OpenAPI schema
]


async def auth_middleware(request: Request, call_next):
    """拦截非白名单路由，校验 Cookie ops_session / Intercept non-whitelisted routes."""
    path = request.url.path

    # 白名单路径放行
    if any(path.startswith(prefix) for prefix in AUTH_WHITELIST):
        return await call_next(request)

    # 静态文件 / 非 API 路由放行（前端资源）
    if not path.startswith("/v1/"):
        return await call_next(request)

    # 校验 session cookie
    token = request.cookies.get("ops_session")
    if not token:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {"code": "4001", "msg": "Not authenticated"},
                "data": None,
            },
        )

    user_id = await redis_store.get_session(token)
    if user_id is None:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {"code": "4001", "msg": "Session expired"},
                "data": None,
            },
        )

    # 注入 user_id 到 request state
    request.state.user_id = user_id
    return await call_next(request)

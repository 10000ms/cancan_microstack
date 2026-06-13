"""认证 HTTP handler / Authentication API handlers."""
import http

from fastapi import Request, Response

from linglong_web import build_success_response, LinglongConfig

from cancan_microstack.public.const.opsbffsrv_error import OpsbffsrvAuthErrorCode
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.application import auth_app
from cancan_microstack.services.opsbffsrv.application.auth_app import (
    LoginRequest,
    TempTokenRequest,
    TotpCodeRequest,
)


def get_client_ip(request: Request) -> str:
    """从 X-Forwarded-For → X-Real-IP → direct 依次读取真实客户端 IP。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    """设置 session Cookie / Set ops_session cookie on response."""
    session_ttl = int(LinglongConfig.get("AUTH_SESSION_TTL", 86400))
    cookie_secure = str(LinglongConfig.get("AUTH_COOKIE_SECURE", "true")).lower() == "true"
    response.set_cookie(
        key="ops_session",
        value=token,
        httponly=True,
        secure=cookie_secure,
        path="/",
        max_age=session_ttl,
        samesite="lax",
    )


async def get_captcha_handler():
    """GET /v1/opsbffsrv/auth/captcha — 返回验证码图片"""
    result = await auth_app.get_captcha()
    return build_success_response(data=result)


async def login_handler(request: Request, payload: LoginRequest):
    """POST /v1/opsbffsrv/auth/login — 登录（用户名+密码+验证码）"""
    client_ip = get_client_ip(request)
    result = await auth_app.login(payload, client_ip)
    return build_success_response(data=result)


async def totp_setup_handler(payload: TempTokenRequest):
    """POST /v1/opsbffsrv/auth/totp/setup — 获取 TOTP 绑定二维码"""
    result = await auth_app.totp_setup(payload.temp_token)
    return build_success_response(data=result)


async def totp_bind_handler(response: Response, payload: TotpCodeRequest):
    """POST /v1/opsbffsrv/auth/totp/bind — 完成 TOTP 绑定"""
    session_token = await auth_app.totp_bind(payload.temp_token, payload.totp_code)
    _set_session_cookie(response, session_token)
    return build_success_response(data={"message": "TOTP bound successfully"})


async def totp_verify_handler(response: Response, payload: TotpCodeRequest):
    """POST /v1/opsbffsrv/auth/totp/verify — 常规 TOTP 验证"""
    session_token = await auth_app.totp_verify(payload.temp_token, payload.totp_code)
    _set_session_cookie(response, session_token)
    return build_success_response(data={"message": "TOTP verified successfully"})


async def logout_handler(request: Request, response: Response):
    """POST /v1/opsbffsrv/auth/logout — 登出（撤销 Redis 会话 + 清除 cookie）"""
    token = request.cookies.get("ops_session")
    await auth_app.logout(token)
    # 清除 cookie：复用 Secure 配置，max_age=0 让浏览器立即删除。
    cookie_secure = str(getattr(LinglongConfig, "AUTH_COOKIE_SECURE", "true")).lower() == "true"
    response.set_cookie(
        key="ops_session",
        value="",
        httponly=True,
        secure=cookie_secure,
        path="/",
        max_age=0,
        samesite="lax",
    )
    return build_success_response(data={"message": "Logged out"})


async def check_session_handler(request: Request):
    """GET /v1/opsbffsrv/auth/session — 检查当前 session"""
    token = request.cookies.get("ops_session")
    if not token:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.SESSION_INVALID,
            msg="Not authenticated",
        )

    result = await auth_app.check_session(token)
    if result is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.SESSION_INVALID,
            msg="Session expired",
        )

    return build_success_response(data=result)

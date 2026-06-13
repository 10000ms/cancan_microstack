"""认证用例编排 / Authentication application service (use case orchestration)."""
import http
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from linglong_web import LinglongConfig
from linglong_web.utils import logger

from cancan_microstack.public.const.opsbffsrv_error import OpsbffsrvAuthErrorCode
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.domain.auth import auth_domain
from cancan_microstack.services.opsbffsrv.infrastructure.auth import (
    captcha_service,
    redis_store,
    totp_service,
)
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.admin_user_operate import (
    get_admin_user_by_id,
    mark_totp_bound,
    update_totp_secret,
)


# ── Request / Response schemas ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_id: str
    captcha_answer: str


class LoginResponse(BaseModel):
    next_step: str  # "totp_bind" | "totp_verify"
    temp_token: str


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str


class TotpSetupResponse(BaseModel):
    otpauth_uri: str
    qr_code_base64: str


class TempTokenRequest(BaseModel):
    temp_token: str


class TotpCodeRequest(BaseModel):
    temp_token: str
    totp_code: str


class SessionResponse(BaseModel):
    authenticated: bool
    username: str


# ── Application methods ──────────────────────────────────────────────────────

async def _enforce_totp_attempt_limit(temp_token: str) -> None:
    """TOTP 暴力破解防护：超过上限则失效 temp_token 并拒绝。

    Guard against TOTP brute force: once the per-temp_token failure count
    reaches the configured cap, invalidate the temp_token and reject the request.
    Call this BEFORE verifying the TOTP code on each attempt.
    """
    max_failures = int(getattr(LinglongConfig, "AUTH_TOTP_MAX_FAILURES", 5))
    fail_count = await redis_store.get_totp_fail_count(temp_token)
    if fail_count >= max_failures:
        # 失效 token，强制用户重新走密码登录流程
        await redis_store.delete_temp_token(temp_token)
        await redis_store.reset_totp_fail(temp_token)
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="Too many invalid TOTP attempts; please log in again",
        )


async def _record_totp_failure(temp_token: str) -> None:
    """记录一次 TOTP 失败 / Record one TOTP failure for a temp token."""
    temp_ttl = int(getattr(LinglongConfig, "AUTH_TEMP_TOKEN_TTL", 300))
    await redis_store.increment_totp_fail(temp_token, ttl=temp_ttl)


async def get_captcha() -> CaptchaResponse:
    """生成并存储验证码 / Generate captcha and save to Redis."""
    captcha_id, answer, image_base64 = captcha_service.generate_captcha()
    captcha_ttl = int(LinglongConfig.get("AUTH_CAPTCHA_TTL", 60))
    await redis_store.save_captcha(captcha_id, answer, ttl=captcha_ttl)
    return CaptchaResponse(captcha_id=captcha_id, image_base64=image_base64)


async def login(req: LoginRequest, client_ip: str) -> LoginResponse:
    """登录入口 / Login: validate captcha → authenticate → return next step."""
    # 1. 校验验证码
    if not await auth_domain.validate_captcha(req.captcha_id, req.captcha_answer):
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvAuthErrorCode.CAPTCHA_INVALID,
            msg="Invalid captcha",
        )

    # 2. 认证
    result = await auth_domain.authenticate(req.username, req.password, client_ip)
    if not result.success:
        status = (
            http.HTTPStatus.FORBIDDEN.value
            if result.error_code == "AUTH_IP_LOCKED"
            else http.HTTPStatus.UNAUTHORIZED.value
        )
        code = {
            "AUTH_IP_LOCKED": OpsbffsrvAuthErrorCode.IP_LOCKED,
            "AUTH_CREDENTIALS_INVALID": OpsbffsrvAuthErrorCode.CREDENTIALS_INVALID,
        }.get(result.error_code, OpsbffsrvAuthErrorCode.INTERNAL_ERROR)
        raise HTTPException(status_code=status, error_code=code, msg=result.error_msg)

    # 3. 返回下一步
    next_step = "totp_bind" if not result.totp_bound else "totp_verify"
    return LoginResponse(next_step=next_step, temp_token=result.temp_token)


async def totp_setup(temp_token: str) -> TotpSetupResponse:
    """获取 TOTP 绑定信息 / Get TOTP provisioning URI and QR code."""
    user_id = await redis_store.get_temp_token(temp_token)
    if user_id is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="Temp token invalid or expired",
        )

    user = await get_admin_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="User not found",
        )

    # 如果已有加密 secret 则解密复用，否则生成新的
    if user.totp_secret_encrypted:
        secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    else:
        secret = totp_service.generate_secret()
        encrypted = totp_service.encrypt_secret(secret)
        await update_totp_secret(user.id, encrypted)

    uri = totp_service.get_provisioning_uri(secret, user.username)
    qr_base64 = totp_service.generate_qr_base64(uri)

    return TotpSetupResponse(otpauth_uri=uri, qr_code_base64=qr_base64)


async def totp_bind(temp_token: str, totp_code: str) -> Optional[str]:
    """完成 TOTP 绑定 / Bind TOTP: verify code → mark bound → create session.

    Returns:
        session token string on success.
    """
    user_id = await redis_store.get_temp_token(temp_token)
    if user_id is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="Temp token invalid or expired",
        )

    # 暴力破解防护：超过上限直接失效 token
    await _enforce_totp_attempt_limit(temp_token)

    user = await get_admin_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="User not found",
        )

    if user.totp_bound:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvAuthErrorCode.TOTP_ALREADY_BOUND,
            msg="TOTP already bound",
        )

    if not user.totp_secret_encrypted:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvAuthErrorCode.TOTP_INVALID,
            msg="TOTP has not been set up",
        )

    secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    if not totp_service.verify_totp(secret, totp_code):
        await _record_totp_failure(temp_token)
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvAuthErrorCode.TOTP_INVALID,
            msg="Invalid TOTP code",
        )

    # 绑定成功
    await mark_totp_bound(user.id)
    await redis_store.delete_temp_token(temp_token)
    await redis_store.reset_totp_fail(temp_token)
    session_token = await auth_domain.create_session_token(user.id)
    return session_token


async def totp_verify(temp_token: str, totp_code: str) -> Optional[str]:
    """常规 TOTP 验证 / Verify TOTP for regular login.

    Returns:
        session token string on success.
    """
    user_id = await redis_store.get_temp_token(temp_token)
    if user_id is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="Temp token invalid or expired",
        )

    # 暴力破解防护：超过上限直接失效 token
    await _enforce_totp_attempt_limit(temp_token)

    user = await get_admin_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED.value,
            error_code=OpsbffsrvAuthErrorCode.TEMP_TOKEN_INVALID,
            msg="User not found",
        )

    if not user.totp_secret_encrypted:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvAuthErrorCode.TOTP_INVALID,
            msg="TOTP not configured",
        )

    secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    if not totp_service.verify_totp(secret, totp_code):
        await _record_totp_failure(temp_token)
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvAuthErrorCode.TOTP_INVALID,
            msg="Invalid TOTP code",
        )

    # 验证成功
    await redis_store.delete_temp_token(temp_token)
    await redis_store.reset_totp_fail(temp_token)
    session_token = await auth_domain.create_session_token(user.id)
    return session_token


async def logout(token: Optional[str]) -> None:
    """登出 / Logout: revoke the session token in Redis (idempotent)."""
    if token:
        await auth_domain.revoke_session(token)


async def check_session(token: str) -> Optional[SessionResponse]:
    """检查 session 有效性 / Check if session token is valid.

    Returns:
        SessionResponse if valid, None if invalid.
    """
    user_id = await auth_domain.verify_session(token)
    if user_id is None:
        return None

    user = await get_admin_user_by_id(user_id)
    if user is None:
        return None

    return SessionResponse(authenticated=True, username=user.username)

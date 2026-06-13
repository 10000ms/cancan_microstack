"""认证领域逻辑 / Authentication domain logic."""
from dataclasses import dataclass
from typing import Optional

from nanoid import generate as nanoid_generate

from linglong_web import LinglongConfig

from cancan_microstack.services.opsbffsrv.infrastructure.auth import (
    password_service,
    redis_store,
)
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.admin_user_operate import (
    get_admin_user,
)


@dataclass
class AuthResult:
    """认证结果 / Authentication result."""
    success: bool
    user_id: Optional[int] = None
    totp_bound: bool = False
    error_code: Optional[str] = None
    error_msg: Optional[str] = None
    temp_token: Optional[str] = None


async def check_ip_rate_limit(ip: str) -> bool:
    """检查 IP 是否被锁定 / Check if IP is locked due to too many failures.

    Returns:
        True if locked, False if allowed.
    """
    max_failures = int(LinglongConfig.get("AUTH_IP_MAX_FAILURES", 5))
    count = await redis_store.get_ip_fail_count(ip)
    return count >= max_failures


async def validate_captcha(captcha_id: str, answer: str) -> bool:
    """校验图形验证码 / Validate captcha answer (case-insensitive, one-time use)."""
    stored = await redis_store.get_and_delete_captcha(captcha_id)
    if stored is None:
        return False
    return stored.upper() == answer.upper()


async def authenticate(username: str, password: str, client_ip: str) -> AuthResult:
    """验证用户名密码 / Authenticate user with credentials and IP rate limiting."""
    # 1. 检查 IP 限频
    if await check_ip_rate_limit(client_ip):
        return AuthResult(
            success=False,
            error_code="AUTH_IP_LOCKED",
            error_msg="IP locked for 30 minutes due to too many failed attempts",
        )

    # 2. 查询用户
    user = await get_admin_user(username)
    if user is None:
        lockout_ttl = int(LinglongConfig.get("AUTH_IP_LOCKOUT_TTL", 1800))
        await redis_store.increment_ip_fail(client_ip, ttl=lockout_ttl)
        return AuthResult(
            success=False,
            error_code="AUTH_CREDENTIALS_INVALID",
            error_msg="Invalid credentials",
        )

    # 3. 校验密码
    if not password_service.verify_password(password, user.password_hash):
        lockout_ttl = int(LinglongConfig.get("AUTH_IP_LOCKOUT_TTL", 1800))
        await redis_store.increment_ip_fail(client_ip, ttl=lockout_ttl)
        return AuthResult(
            success=False,
            error_code="AUTH_CREDENTIALS_INVALID",
            error_msg="Invalid credentials",
        )

    # 4. 登录成功，重置 IP 计数，生成临时 token
    await redis_store.reset_ip_fail(client_ip)
    temp_token = nanoid_generate(size=32)
    temp_ttl = int(LinglongConfig.get("AUTH_TEMP_TOKEN_TTL", 300))
    await redis_store.save_temp_token(temp_token, user.id, ttl=temp_ttl)

    return AuthResult(
        success=True,
        user_id=user.id,
        totp_bound=bool(user.totp_bound),
        temp_token=temp_token,
    )


async def create_session_token(user_id: int) -> str:
    """创建 session token / Create session and store in Redis."""
    token = nanoid_generate(size=32)
    session_ttl = int(LinglongConfig.get("AUTH_SESSION_TTL", 86400))
    await redis_store.save_session(token, user_id, ttl=session_ttl)
    return token


async def verify_session(token: str) -> Optional[int]:
    """校验 session token / Verify session token and return user_id or None."""
    return await redis_store.get_session(token)


async def revoke_session(token: str) -> None:
    """撤销 session token / Revoke a session token from Redis."""
    await redis_store.delete_session(token)

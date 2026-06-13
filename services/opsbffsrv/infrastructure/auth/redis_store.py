"""Redis session / 限频 / 验证码存储 / Redis store for auth data."""
from typing import Optional

import redis.asyncio as aioredis

from linglong_web import LinglongConfig

_redis: Optional[aioredis.Redis] = None

_KEY_PREFIX = "ops"


async def _get_redis() -> aioredis.Redis:
    """懒初始化 Redis 连接 / Lazy-initialize async Redis connection."""
    global _redis
    if _redis is None:
        host = LinglongConfig.get("AUTH_REDIS_URL", "redis://redis.service:6379/0")
        _redis = aioredis.from_url(host, decode_responses=True)
    return _redis


# ── Captcha ──────────────────────────────────────────────────────────────────

async def save_captcha(captcha_id: str, answer: str, ttl: int = 60) -> None:
    """存储验证码答案 / Save captcha answer to Redis."""
    r = await _get_redis()
    await r.setex(f"{_KEY_PREFIX}:captcha:{captcha_id}", ttl, answer.upper())


async def get_and_delete_captcha(captcha_id: str) -> Optional[str]:
    """获取并删除验证码（一次性消费）/ Get and delete captcha answer atomically."""
    r = await _get_redis()
    key = f"{_KEY_PREFIX}:captcha:{captcha_id}"
    answer = await r.get(key)
    if answer is not None:
        await r.delete(key)
    return answer


# ── Session ──────────────────────────────────────────────────────────────────

async def save_session(token: str, user_id: int, ttl: int = 86400) -> None:
    """存储 session token / Save session token to Redis."""
    r = await _get_redis()
    await r.setex(f"{_KEY_PREFIX}:session:{token}", ttl, str(user_id))


async def get_session(token: str) -> Optional[int]:
    """获取 session 对应的 user_id / Get user_id from session token."""
    r = await _get_redis()
    val = await r.get(f"{_KEY_PREFIX}:session:{token}")
    return int(val) if val is not None else None


async def delete_session(token: str) -> None:
    """删除 session token / Delete (revoke) a session token."""
    r = await _get_redis()
    await r.delete(f"{_KEY_PREFIX}:session:{token}")


# ── Temp Token ───────────────────────────────────────────────────────────────

async def save_temp_token(token: str, user_id: int, ttl: int = 300) -> None:
    """存储临时 token / Save temp token for TOTP flow."""
    r = await _get_redis()
    await r.setex(f"{_KEY_PREFIX}:temp_token:{token}", ttl, str(user_id))


async def get_temp_token(token: str) -> Optional[int]:
    """获取临时 token 对应的 user_id / Get user_id from temp token."""
    r = await _get_redis()
    val = await r.get(f"{_KEY_PREFIX}:temp_token:{token}")
    return int(val) if val is not None else None


async def delete_temp_token(token: str) -> None:
    """删除临时 token / Delete temp token."""
    r = await _get_redis()
    await r.delete(f"{_KEY_PREFIX}:temp_token:{token}")


# ── IP Rate Limit ────────────────────────────────────────────────────────────

async def get_ip_fail_count(ip: str) -> int:
    """获取 IP 失败次数 / Get login failure count for an IP."""
    r = await _get_redis()
    val = await r.get(f"{_KEY_PREFIX}:rate_limit:ip:{ip}")
    return int(val) if val is not None else 0


async def increment_ip_fail(ip: str, ttl: int = 1800) -> int:
    """递增 IP 失败计数 / Increment IP failure count with TTL."""
    r = await _get_redis()
    key = f"{_KEY_PREFIX}:rate_limit:ip:{ip}"
    count = await r.incr(key)
    await r.expire(key, ttl)
    return count


async def reset_ip_fail(ip: str) -> None:
    """重置 IP 失败计数 / Reset IP failure count."""
    r = await _get_redis()
    await r.delete(f"{_KEY_PREFIX}:rate_limit:ip:{ip}")


# ── TOTP Failure Count (per temp_token) ───────────────────────────────────────

async def get_totp_fail_count(temp_token: str) -> int:
    """获取 temp_token 的 TOTP 失败次数 / Get TOTP failure count for a temp token."""
    r = await _get_redis()
    val = await r.get(f"{_KEY_PREFIX}:totp_fail:{temp_token}")
    return int(val) if val is not None else 0


async def increment_totp_fail(temp_token: str, ttl: int = 300) -> int:
    """递增 TOTP 失败计数 / Increment TOTP failure count with TTL.

    TTL 跟随 temp_token 生命周期，避免计数长期残留。
    TTL follows the temp_token lifetime so the counter does not linger.
    """
    r = await _get_redis()
    key = f"{_KEY_PREFIX}:totp_fail:{temp_token}"
    count = await r.incr(key)
    await r.expire(key, ttl)
    return count


async def reset_totp_fail(temp_token: str) -> None:
    """重置 TOTP 失败计数 / Reset TOTP failure count for a temp token."""
    r = await _get_redis()
    await r.delete(f"{_KEY_PREFIX}:totp_fail:{temp_token}")

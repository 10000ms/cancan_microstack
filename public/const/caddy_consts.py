"""
Caddy service related constants.
"""
from enum import StrEnum


class SecurityEventType(StrEnum):
    """Security event types for Caddy logs."""
    WAF_BLOCKED = "waf_blocked"
    RATE_LIMITED = "rate_limited"


class InternalRequestPath(StrEnum):
    """内部系统路径常量
    Internal system request path constants
    """

    HEALTH_CHECK = "/internal/health"
    INTERNAL_PREFIX = "/internal/"
    OPSBFF_API_PREFIX = "/v1/opsbffsrv/"
    INTERNAL_SQL_LIKE = "/internal/%"
    OPSBFF_API_SQL_LIKE = "/v1/opsbffsrv/%"

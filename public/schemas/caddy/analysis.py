"""
Pydantic models for Caddy log analysis.
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)
from pydantic import BaseModel


class SuspiciousIP(BaseModel):
    """Data model for a suspicious IP address."""
    ip: str
    count: int


class ErrorPatternAnalysis(BaseModel):
    """Data model for error pattern analysis results."""
    total_errors: int
    error_rate: float
    top_error_paths: List[Tuple[str, int]]
    error_by_status: Dict[int, int]


class RealtimeStatsMetadata(BaseModel):
    """实时统计元数据
    Realtime statistics metadata
    """

    realtime_window_minutes: int


class TopCountryStatsMetadata(BaseModel):
    """Top 国家统计元数据
    Top country statistics metadata
    """

    country: str
    country_name: str
    country_code: str
    count: int
    percentage: float


class TopIPStatsMetadata(BaseModel):
    """Top IP 统计元数据
    Top IP statistics metadata
    """

    client_ip: str
    country: str
    city: str
    count: int
    percentage: float


class StatsAggregationPayload(BaseModel):
    """统计聚合载荷模型
    Typed payload for CaddyStats numeric fields
    """

    total_requests: int = 0
    success_requests: int = 0
    client_error_requests: int = 0
    server_error_requests: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    avg_response_time: Optional[int] = 0
    min_response_time: Optional[int] = 0
    max_response_time: Optional[int] = 0
    p50_response_time: Optional[int] = 0
    p95_response_time: Optional[int] = 0
    p99_response_time: Optional[int] = 0
    waf_blocked_requests: int = 0
    waf_logged_requests: int = 0
    rate_limited_requests: int = 0
    tls_requests: int = 0
    non_tls_requests: int = 0
    unique_ips: int = 0
    unique_user_agents: int = 0

    def to_stats_dict(self) -> Dict[str, Any]:
        """导出 CaddyStats 可用字段字典
        Export payload as CaddyStats-compatible dict
        """

        return self.model_dump()

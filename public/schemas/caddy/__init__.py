"""
Caddy 相关的 Pydantic 类型定义
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import datetime
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from decimal import Decimal


# ==================== Caddy Route（路由） ====================

class CaddyRouteCreate(BaseModel):
    """创建路由的请求模型"""
    route_name: str = Field(..., description="路由名称（唯一标识）", min_length=1, max_length=100)
    domain: str = Field(..., description="域名", min_length=1, max_length=255)
    path_pattern: str = Field(..., description="路径匹配模式", min_length=1, max_length=500)
    upstream_service: str = Field(..., description="上游服务名称", min_length=1, max_length=100)
    upstream_host: str = Field(..., description="上游主机", min_length=1, max_length=100)
    upstream_port: int = Field(..., description="上游端口", ge=1, le=65535)
    strip_path_prefix: Optional[str] = Field(None, description="去除路径前缀", max_length=200)
    add_path_prefix: Optional[str] = Field(None, description="添加路径前缀", max_length=200)
    enable_https: bool = Field(default=True, description="是否启用 HTTPS")
    force_https: bool = Field(default=True, description="是否强制 HTTPS")
    enable_waf: bool = Field(default=True, description="是否启用 WAF")
    waf_rule_set: str = Field(default="default", description="WAF 规则集")
    load_balance_strategy: str = Field("round_robin", description="负载均衡策略")
    health_check_path: Optional[str] = Field(default=None, description="健康检查路径", max_length=200)
    health_check_interval: int = Field(default=30, description="健康检查间隔（秒）", ge=5)
    is_enabled: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=100, description="优先级", ge=0)
    route_metadata: Optional[Dict[str, Any]] = Field(default=None, description="路由附加元数据")
    description: Optional[str] = Field(default=None, description="路由描述")


class CaddyRouteUpdate(BaseModel):
    """更新路由的请求模型（所有字段可选）"""
    domain: Optional[str] = Field(None, description="域名", min_length=1, max_length=255)
    path_pattern: Optional[str] = Field(None, description="路径匹配模式", min_length=1, max_length=500)
    upstream_service: Optional[str] = Field(None, description="上游服务名称", min_length=1, max_length=100)
    upstream_host: Optional[str] = Field(None, description="上游主机", min_length=1, max_length=100)
    upstream_port: Optional[int] = Field(None, description="上游端口", ge=1, le=65535)
    strip_path_prefix: Optional[str] = Field(None, description="去除路径前缀", max_length=200)
    add_path_prefix: Optional[str] = Field(None, description="添加路径前缀", max_length=200)
    enable_https: Optional[bool] = Field(None, description="是否启用 HTTPS")
    force_https: Optional[bool] = Field(None, description="是否强制 HTTPS")
    enable_waf: Optional[bool] = Field(None, description="是否启用 WAF")
    waf_rule_set: Optional[str] = Field(None, description="WAF 规则集")
    load_balance_strategy: Optional[str] = Field(None, description="负载均衡策略")
    health_check_path: Optional[str] = Field(None, description="健康检查路径", max_length=200)
    health_check_interval: Optional[int] = Field(None, description="健康检查间隔（秒）", ge=5)
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    priority: Optional[int] = Field(None, description="优先级", ge=0)
    route_metadata: Optional[Dict[str, Any]] = Field(None, description="路由附加元数据")
    description: Optional[str] = Field(None, description="路由描述")


class CaddyRoute(BaseModel):
    """路由数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    route_name: str
    domain: str
    path_pattern: str
    upstream_service: str
    upstream_host: str
    upstream_port: int
    strip_path_prefix: Optional[str] = None
    add_path_prefix: Optional[str] = None
    enable_https: bool = True
    force_https: bool = True
    enable_waf: bool = True
    waf_rule_set: str = "default"
    load_balance_strategy: str = "round_robin"
    health_check_path: Optional[str] = None
    health_check_interval: int = 30
    is_enabled: bool = True
    priority: int = 100
    route_metadata: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



# ==================== Caddy Rate Limit（限流） ====================

class CaddyRateLimitCreate(BaseModel):
    """创建限流规则的请求模型"""
    rule_name: str = Field(..., description="规则名称（唯一标识）", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="规则描述")
    match_type: str = Field(..., description="匹配类型（path/domain/ip/header/all）")
    match_pattern: Optional[str] = Field(None, description="匹配模式", max_length=500)
    match_domain: Optional[str] = Field(None, description="匹配域名", max_length=255)
    limit_type: str = Field("request", description="限流类型（request/bandwidth）")
    limit_value: int = Field(..., description="限流值", ge=1)
    limit_window: int = Field(60, description="时间窗口（秒）", ge=1)
    limit_key: str = Field("ip", description="限流键（ip/header/cookie/path）")
    burst_size: int = Field(0, description="突发流量大小", ge=0)
    block_status_code: int = Field(429, description="被限流时的状态码", ge=100, le=599)
    block_message: str = Field("Too Many Requests", description="被限流时的消息", max_length=500)
    whitelist_ips: Optional[List[str]] = Field(None, description="IP 白名单")
    blacklist_ips: Optional[List[str]] = Field(None, description="IP 黑名单")
    is_enabled: bool = Field(True, description="是否启用")
    priority: int = Field(100, description="优先级", ge=0)
    rule_metadata: Optional[Dict[str, Any]] = Field(default=None, description="限流附加元数据")


class CaddyRateLimitUpdate(BaseModel):
    """更新限流规则的请求模型（所有字段可选）"""
    description: Optional[str] = Field(None, description="规则描述")
    match_type: Optional[str] = Field(None, description="匹配类型（path/domain/ip/header/all）")
    match_pattern: Optional[str] = Field(None, description="匹配模式", max_length=500)
    match_domain: Optional[str] = Field(None, description="匹配域名", max_length=255)
    limit_type: Optional[str] = Field(None, description="限流类型（request/bandwidth）")
    limit_value: Optional[int] = Field(None, description="限流值", ge=1)
    limit_window: Optional[int] = Field(None, description="时间窗口（秒）", ge=1)
    limit_key: Optional[str] = Field(None, description="限流键（ip/header/cookie/path）")
    burst_size: Optional[int] = Field(None, description="突发流量大小", ge=0)
    block_status_code: Optional[int] = Field(None, description="被限流时的状态码", ge=100, le=599)
    block_message: Optional[str] = Field(None, description="被限流时的消息", max_length=500)
    whitelist_ips: Optional[List[str]] = Field(None, description="IP 白名单")
    blacklist_ips: Optional[List[str]] = Field(None, description="IP 黑名单")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    priority: Optional[int] = Field(None, description="优先级", ge=0)
    rule_metadata: Optional[Dict[str, Any]] = Field(None, description="限流附加元数据")


class CaddyRateLimit(BaseModel):
    """限流规则数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    rule_name: str
    description: Optional[str] = None
    match_type: str
    match_pattern: Optional[str] = None
    match_domain: Optional[str] = None
    limit_type: str = "request"
    limit_value: int
    limit_window: int = 60
    limit_key: str = "ip"
    burst_size: int = 0
    block_status_code: int = 429
    block_message: str = "Too Many Requests"
    whitelist_ips: Optional[List[str]] = None
    blacklist_ips: Optional[List[str]] = None
    is_enabled: bool = True
    priority: int = 100
    rule_metadata: Optional[Dict[str, Any]] = None
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



# ==================== Caddy Access Log（访问日志） ====================

class CaddyAccessLog(BaseModel):
    """访问日志数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    request_id: str
    timestamp: datetime
    client_ip: str
    client_port: Optional[int] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    timezone: Optional[str] = None
    isp: Optional[str] = None
    method: str
    protocol: Optional[str] = None
    host: Optional[str] = None
    path: str
    query_string: Optional[str] = None
    matched_route: Optional[str] = None
    upstream_service: Optional[str] = None
    upstream_host: Optional[str] = None
    upstream_port: Optional[int] = None
    status_code: int
    response_size: Optional[int] = None
    response_time: Optional[int] = None
    waf_action: Optional[str] = None
    waf_rule_id: Optional[str] = None
    waf_score: Optional[int] = None
    rate_limited: bool = False
    rate_limit_rule: Optional[str] = None
    tls_version: Optional[str] = None
    tls_cipher: Optional[str] = None
    log_metadata: Optional[Dict[str, Any]] = None
    created_time: Optional[datetime] = None



# ==================== Caddy Stats（统计） ====================

class CaddyStats(BaseModel):
    """统计数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    stat_time: datetime
    stat_period: str
    dimension_type: str
    dimension_value: Optional[str] = None
    total_requests: int = 0
    success_requests: int = 0
    client_error_requests: int = 0
    server_error_requests: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    avg_response_time: Optional[int] = None
    min_response_time: Optional[int] = None
    max_response_time: Optional[int] = None
    p50_response_time: Optional[int] = None
    p95_response_time: Optional[int] = None
    p99_response_time: Optional[int] = None
    waf_blocked_requests: int = 0
    waf_logged_requests: int = 0
    rate_limited_requests: int = 0
    tls_requests: int = 0
    non_tls_requests: int = 0
    unique_ips: int = 0
    unique_user_agents: int = 0
    stats_metadata: Optional[Dict[str, Any]] = None
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



class RealtimeStatsResponse(BaseModel):
    """实时统计响应模型
    Realtime statistics response model
    """

    stats: Optional[CaddyStats] = Field(default=None, description="统计数据 / Statistics payload")


class GlobalTrendResponse(BaseModel):
    """全局趋势响应模型
    Global trend response model
    """

    period: str = Field(..., description="统计周期（hourly/daily/monthly）/ Aggregation period")
    hours: int = Field(..., description="聚合的小时数 / Number of aggregated hours")
    trend: List[CaddyStats] = Field(default_factory=list, description="统计数据序列 / Statistics series")


class ServiceTrendResponse(GlobalTrendResponse):
    """服务趋势响应模型
    Service trend response model
    """

    service_name: str = Field(..., description="服务名称 / Service name")


class RouteTrendResponse(GlobalTrendResponse):
    """路由趋势响应模型
    Route trend response model
    """

    route_id: int = Field(..., description="路由 ID / Route identifier")


class TopDimensionResponse(BaseModel):
    """Top 维度统计响应模型
    Top dimension statistics response model
    """

    period: str = Field(..., description="统计周期 / Aggregation period")
    limit: int = Field(..., description="返回数量上限 / Maximum number of items")
    items: List[CaddyStats] = Field(default_factory=list, description="统计项列表 / Statistics items")


class CleanupStatsResponse(BaseModel):
    """统计数据清理结果模型
    Cleanup statistics response model
    """

    message: str = Field(..., description="执行结果信息 / Result message")


# ==================== Caddy Certificate（证书） ====================

class CaddyCertificateCreate(BaseModel):
    """创建证书的请求模型"""
    domain: str = Field(..., description="主域名", min_length=1, max_length=255)
    alt_domains: Optional[List[str]] = Field(None, description="备用域名列表")
    auto_renew: bool = Field(True, description="是否自动续期")
    renew_before_days: int = Field(30, description="提前多少天续期", ge=1, le=90)
    acme_provider: str = Field("letsencrypt", description="ACME 提供商")
    acme_email: Optional[str] = Field(None, description="ACME 邮箱", max_length=255)
    acme_challenge_type: str = Field("http-01", description="ACME 挑战类型（http-01/dns-01）")
    certificate_metadata: Optional[Dict[str, Any]] = Field(None, description="证书附加元数据")


class CaddyCertificateUpdate(BaseModel):
    """更新证书的请求模型（所有字段可选）"""
    alt_domains: Optional[List[str]] = Field(None, description="备用域名列表")
    auto_renew: Optional[bool] = Field(None, description="是否自动续期")
    renew_before_days: Optional[int] = Field(None, description="提前多少天续期", ge=1, le=90)
    acme_provider: Optional[str] = Field(None, description="ACME 提供商")
    acme_email: Optional[str] = Field(None, description="ACME 邮箱", max_length=255)
    acme_challenge_type: Optional[str] = Field(None, description="ACME 挑战类型（http-01/dns-01）")
    certificate_metadata: Optional[Dict[str, Any]] = Field(None, description="证书附加元数据")


class CaddyCertificate(BaseModel):
    """证书数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    domain: str
    alt_domains: Optional[List[str]] = None
    certificate_pem: Optional[str] = None
    private_key_pem: Optional[str] = None
    issuer: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    auto_renew: bool = True
    renew_before_days: int = 30
    status: str = "pending"
    last_renew_attempt: Optional[datetime] = None
    last_renew_success: Optional[datetime] = None
    renew_error: Optional[str] = None
    acme_provider: str = "letsencrypt"
    acme_email: Optional[str] = None
    acme_challenge_type: str = "http-01"
    certificate_metadata: Optional[Dict[str, Any]] = None
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



# ==================== 查询参数模型 ====================

class AccessLogQuery(BaseModel):
    """访问日志查询参数"""
    client_ip: Optional[str] = Field(default=None, description="客户端 IP")
    country: Optional[str] = Field(default=None, description="国家")
    country_code: Optional[str] = Field(default=None, description="国家代码")
    upstream_service: Optional[str] = Field(default=None, description="上游服务")
    matched_route: Optional[str] = Field(default=None, description="匹配的路由")
    waf_action: Optional[str] = Field(default=None, description="WAF 动作")
    rate_limited: Optional[bool] = Field(default=None, description="是否被限流")
    min_response_time: Optional[int] = Field(default=None, description="最小响应时间（毫秒）")
    max_response_time: Optional[int] = Field(default=None, description="最大响应时间（毫秒）")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    limit: int = Field(default=100, description="返回数量限制", ge=1, le=1000)
    offset: int = Field(default=0, description="偏移量", ge=0)


class StatsQuery(BaseModel):
    """统计数据查询参数"""
    stat_period: Optional[str] = Field(None, description="统计周期（minute/hour/day/month）")
    dimension_type: Optional[str] = Field(None, description="维度类型（global/service/route/ip/country）")
    dimension_value: Optional[str] = Field(None, description="维度值")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    limit: int = Field(100, description="返回数量限制", ge=1, le=1000)

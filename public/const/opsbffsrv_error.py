"""Opsbffsrv 模块错误码枚举 / Error code enumerations for opsbffsrv."""
from enum import StrEnum


class OpsbffsrvInstanceErrorCode(StrEnum):
    """实例管理错误码 / Instance management error codes."""

    LIST_HTTP_ERROR = "50001"  # 获取实例列表失败 / Failed to fetch instance list
    INTERNAL_ERROR = "50000"  # 实例管理内部错误 / Internal instance management error
    DETAIL_HTTP_ERROR = "50002"  # 获取实例详情失败 / Failed to fetch instance detail
    STATS_HTTP_ERROR = "50003"  # 获取实例统计信息失败 / Failed to fetch instance statistics


class OpsbffsrvServiceLogsErrorCode(StrEnum):
    """服务日志错误码 / Service logs error codes."""

    INVALID_INPUT = "10001"  # 输入参数无效 / Invalid input parameter
    INFRA_HTTP_ERROR = "10002"  # 调用 infrasrv HTTP 出错 / HTTP error when calling infrasrv
    INFRA_RESPONSE_ERROR = "10003"  # infrasrv 返回失败 / infrasrv responded with failure
    INTERNAL_ERROR = "10004"  # 服务日志内部错误 / Internal service log error


class OpsbffsrvServiceConfigErrorCode(StrEnum):
    """服务配置错误码 / Service configuration error codes."""

    INVALID_INPUT = "20001"  # 输入参数无效 / Invalid input parameter
    INTERNAL_ERROR = "20002"  # 服务配置内部错误 / Internal service configuration error
    PUSH_TRIGGER_FAILED = "20003"  # 配置推送触发失败 / Failed to trigger config push


class OpsbffsrvDbAdminErrorCode(StrEnum):
    """数据库管理错误码 / Database administration error codes."""

    SCHEMA_APPLY_FAILED = "30001"  # 模式应用失败 / Schema apply operation failed
    SCHEMA_DIFF_FAILED = "30002"  # 模式对比失败 / Schema diff operation failed
    DATABASE_REBUILD_FAILED = "30003"  # 数据库重建失败 / Database rebuild operation failed
    TABLE_REBUILD_FAILED = "30004"  # 数据表重建失败 / Table rebuild operation failed


class OpsbffsrvCaddyRouteErrorCode(StrEnum):
    """Caddy 路由错误码 / Caddy route management error codes."""

    CREATE_VALIDATION_FAILED = "40001"  # 路由创建参数校验失败 / Route creation validation failed
    CREATE_SYNC_FAILED = "50001"  # 路由创建同步失败 / Route creation sync failure
    UPDATE_VALIDATION_FAILED = "40002"  # 路由更新参数校验失败 / Route update validation failed
    UPDATE_SYNC_FAILED = "50002"  # 路由更新同步失败 / Route update sync failure
    ROUTE_NOT_FOUND = "40401"  # 路由不存在 / Route not found
    ROUTE_QUERY_FAILED = "50003"  # 路由查询失败 / Route query failure
    ROUTE_DELETE_FAILED = "50004"  # 路由删除失败 / Route deletion failure
    ROUTE_TOGGLE_VALIDATION_FAILED = "40003"  # 路由状态切换参数校验失败 / Route toggle validation failed
    ROUTE_TOGGLE_FAILED = "50005"  # 路由状态切换失败 / Route toggle failure


class OpsbffsrvCaddyStatsErrorCode(StrEnum):
    """Caddy 统计错误码 / Caddy statistics error codes."""

    REALTIME_GLOBAL_FAILED = "50301"  # 获取实时全局统计失败 / Failed to fetch realtime global stats
    REALTIME_SERVICE_NOT_FOUND = "40401"  # 服务统计不存在 / Service statistics not found
    REALTIME_SERVICE_FAILED = "50302"  # 获取实时服务统计失败 / Failed to fetch realtime service stats
    GLOBAL_TREND_FAILED = "50303"  # 获取全局趋势失败 / Failed to fetch global trend
    SERVICE_TREND_FAILED = "50304"  # 获取服务趋势失败 / Failed to fetch service trend
    ROUTE_TREND_FAILED = "50305"  # 获取路由趋势失败 / Failed to fetch route trend
    TOP_COUNTRY_FAILED = "50306"  # 获取 Top 国家失败 / Failed to fetch top countries
    TOP_IP_FAILED = "50307"  # 获取 Top IP 失败 / Failed to fetch top IPs
    CLEANUP_FAILED = "50308"  # 清理统计数据失败 / Failed to cleanup statistics


class OpsbffsrvCaddyAccessLogErrorCode(StrEnum):
    """Caddy 访问日志错误码 / Caddy access log error codes."""

    SEARCH_FAILED = "50401"  # 搜索访问日志失败 / Failed to search access logs
    SECURITY_EVENT_FAILED = "50402"  # 获取安全事件失败 / Failed to fetch security events
    GEO_ANALYSIS_FAILED = "50403"  # 分析地理分布失败 / Failed to analyze geographic distribution
    STATUS_CODE_ANALYSIS_FAILED = "50404"  # 分析状态码分布失败 / Failed to analyze status code distribution
    SUSPICIOUS_IP_FAILED = "50405"  # 检测可疑 IP 失败 / Failed to detect suspicious IPs
    ERROR_PATTERN_ANALYSIS_FAILED = "50406"  # 分析错误模式失败 / Failed to analyze error patterns
    CLEANUP_LOG_FAILED = "50407"  # 清理访问日志失败 / Failed to cleanup access logs


class OpsbffsrvAuthErrorCode(StrEnum):
    """认证错误码 / Authentication error codes."""

    CAPTCHA_INVALID = "60001"      # 验证码错误 / Invalid captcha
    CREDENTIALS_INVALID = "60002"  # 用户名或密码错误 / Invalid credentials
    IP_LOCKED = "60003"            # IP 被锁定 / IP locked
    TEMP_TOKEN_INVALID = "60004"   # 临时 token 无效 / Temp token invalid
    TOTP_INVALID = "60005"         # TOTP 验证码错误 / Invalid TOTP code
    TOTP_ALREADY_BOUND = "60006"   # TOTP 已绑定 / TOTP already bound
    SESSION_INVALID = "60007"      # Session 无效 / Invalid session
    INTERNAL_ERROR = "60099"       # 认证内部错误 / Authentication internal error



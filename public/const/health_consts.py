from enum import StrEnum


class HealthCheckResult(StrEnum):
    """
    健康检查结果枚举
    Enum for health check result values
    """
    PASS = "PASS"
    FAIL = "FAIL"


class HealthOverallStatus(StrEnum):
    """
    服务整体状态枚举
    Enum for overall service status used in overviews
    """
    UP = "UP"
    PARTIAL = "PARTIAL"
    DOWN = "DOWN"


# 更多健康状态，用于实例级别标记
class InstanceHealthStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    EXEMPTED = "exempted"
    EXPECTED_STOPPED = "expected_stopped"


class ServiceRuntimeStatus(StrEnum):
    """
    服务运行时状态（用于概览的 expected/actual）
    Runtime service status for overview expected/actual fields
    """

    RUNNING = "running"
    STOPPED = "stopped"
    DEGRADED = "degraded"


class ServiceExpectedStatusAlias(StrEnum):
    """
    期望状态别名（用于标准化输入）
    Expected status aliases for normalization
    """

    STOP = "stop"
    STOPPED = "stopped"
    DOWN = "down"

"""
Logging-related enums.
"""
from enum import StrEnum


class LogLevel(StrEnum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
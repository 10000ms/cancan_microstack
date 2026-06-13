"""
异步操作相关的常量和枚举定义
"""
from enum import StrEnum


class OperationType(StrEnum):
    """操作类型枚举"""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    LIST = "list"
    HEALTH = "health"
    COMPOSE_STATUS = "compose_status"


class OperationStatus(StrEnum):
    """操作状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class InitiatedBy(StrEnum):
    """操作发起者枚举"""
    OPSBFFSRV = "opsbffsrv"
    INFRASRV = "infrasrv"
    CONTROLLERSRV = "controllersrv"
    SYSTEM = "system"
    USER = "user"
    INFRASRV_HEALTH_CHECK = "infrasrv_health_check"


class InitiatedFrom(StrEnum):
    """发起来源枚举"""
    FRONTEND = "frontend"
    API = "api"
    SCHEDULER = "scheduler"
    WEBHOOK = "webhook"
    INTERNAL = "internal"
    HEALTH_CHECK_DOMAIN = "health_check_domain"


# 操作超时时间配置（秒）
OPERATION_TIMEOUTS = {
    OperationType.START: 120,
    OperationType.STOP: 60,
    OperationType.RESTART: 180,
}

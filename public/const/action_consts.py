from enum import StrEnum


class ActionType(StrEnum):
    REGISTER = "register"
    DEREGISTER = "deregister"
    HEARTBEAT = "heartbeat"
    HEALTH_CHECK_FAIL = "health_check_fail"
    AUTO_RESTART = "auto_restart"
    START = "start"
    STOP = "stop"
    RESTART = "restart"


class HealthCheckAction(StrEnum):
    """健康检查采取的操作"""
    AUTO_STOP_SCHEDULED = "auto_stop_scheduled"
    AUTO_RESTART_SCHEDULED = "auto_restart_scheduled"
from enum import StrEnum


class PushStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class InstanceStatus(StrEnum):
    """服务实例状态枚举"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UNHEALTHY = "unhealthy"

"""
Monitor-related enums.
"""
from enum import StrEnum


class ContainerStatus(StrEnum):
    """容器状态枚举"""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    STARTING = "starting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"
    CREATED = "created"
    UNKNOWN = "unknown"


class CleanupPolicy(StrEnum):
    """清理策略枚举"""
    NEVER = "never"           # 从不清理
    ON_FAILURE = "failure"    # 失败时清理
    ON_EXIT = "exit"          # 退出时清理
    ALWAYS = "always"        # 总是清理

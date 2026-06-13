"""
Docker相关常量定义
"""
from enum import StrEnum


class DockerLabel(StrEnum):
    """Docker Compose labels used for identifying services."""
    SERVICE = "com.docker.compose.service"


class DockerInspectKey(StrEnum):
    """Keys used for inspecting Docker container details."""
    STATE = "State"
    HEALTH = "Health"

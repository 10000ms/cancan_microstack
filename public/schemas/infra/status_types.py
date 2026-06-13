"""
Defines enumeration types for service and container statuses.
"""
from enum import StrEnum


class InstanceStatus(StrEnum):
    """Represents the status of a service instance as stored in the database."""
    UP = "UP"
    DOWN = "DOWN"
    UNHEALTHY = "UNHEALTHY"


class ContainerStatus(StrEnum):
    """Represents the status of a container, including expected and observed states."""
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"
    ERROR = "error"

"""
Container related types
"""
from typing import Optional
from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class ContainerState(BaseModel):
    """Represents the state of a container at a point in time."""
    name: str = Field(description="容器名称")
    status: str = Field(description="容器状态 (e.g., 'running', 'exited', 'unknown', 'error')")
    running: bool = Field(description="容器是否正在运行")
    is_healthy: bool = Field(default=False, description="容器是否健康")
    error: Optional[str] = Field(default=None, description="检查时发生的错误信息")
    checked_at: datetime = Field(default_factory=datetime.now, description="状态检查时间")
    
    # Fields from container_info.to_dict() that might be useful
    id: Optional[str] = None
    paused: bool = False
    restarting: bool = False
    oom_killed: bool = False
    exit_code: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    health: Optional[dict] = None
    network_settings: Optional[dict] = None
    ports: Optional[dict] = None
    labels: Optional[dict] = None
    created: Optional[str] = None

    class Config:
        from_attributes = True


class FullContainerState(ContainerState):
    """Represents the combined state of a container and its service instance."""
    instance_id: Optional[str] = None
    service_name: Optional[str] = None
    expected_status: Optional[str] = None
    db_status: Optional[str] = None


class ContainerStateCacheEntry(BaseModel):
    """Represents a cache entry for a container's state."""
    state: ContainerState
    timestamp: datetime


class InconsistentInstanceInfo(BaseModel):
    """Represents information about an instance with inconsistent state."""
    instance_id: str
    service_name: str
    container_name: str
    db_status: str
    expected_status: str
    container_status: Optional[str] = None
    container_running: bool
    container_healthy: bool
    inconsistency_reason: str


class CleanedInstanceInfo(BaseModel):
    """Represents information about a cleaned-up instance."""
    instance_id: str
    service_name: str
    container_name: str
    exit_code: Optional[int] = None
    finished_at: Optional[str] = None
    reason: str

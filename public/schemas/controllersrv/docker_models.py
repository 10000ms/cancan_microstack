"""
Docker-specific domain models for controllersrv.
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)


class HealthCheck(BaseModel):
    """Container health check status."""
    status: str = Field(..., alias='Status')
    failing_streak: int = Field(..., alias='FailingStreak')
    log: List[Dict[str, Any]] = Field(..., alias='Log')


class ContainerState(BaseModel):
    """Container state information."""
    status: str = Field(..., alias='Status')
    running: bool = Field(..., alias='Running')
    paused: bool = Field(..., alias='Paused')
    restarting: bool = Field(..., alias='Restarting')
    oom_killed: bool = Field(..., alias='OOMKilled')
    dead: bool = Field(..., alias='Dead')
    pid: int = Field(..., alias='Pid')
    exit_code: int = Field(..., alias='ExitCode')
    error: str = Field(..., alias='Error')
    started_at: str = Field(..., alias='StartedAt')
    finished_at: str = Field(..., alias='FinishedAt')
    health: Optional[HealthCheck] = Field(None, alias='Health')


class ContainerHealthDetail(BaseModel):
    """Detailed container health information."""
    id: str
    name: str
    state: Optional[ContainerState] = None
    health: Optional[HealthCheck] = None

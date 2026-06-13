from typing import (
    List,
    Optional,
)
from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class CleanupDetail(BaseModel):
    service_name: str = Field(...)
    instance_id: str = Field(...)
    action: str = Field(...)
    reason: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


class CleanupResult(BaseModel):
    total_checked: int = Field(...)
    cleaned: int = Field(default=0)
    kept: int = Field(default=0)
    details: List[CleanupDetail] = Field(default_factory=list)

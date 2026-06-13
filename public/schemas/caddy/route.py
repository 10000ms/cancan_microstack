from typing import (
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)



class ToggleRoutePayload(BaseModel):
    """切换路由状态请求体 / Toggle route state request payload"""

    enabled: Optional[bool] = Field(
        default=None,
        description="目标启用状态，为空时自动取反 / Desired enabled state, auto-toggle when omitted",
    )

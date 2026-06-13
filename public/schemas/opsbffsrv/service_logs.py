from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.schemas.infra.service_action_log import ServiceActionLog


class ServiceLogsQueryContext(BaseModel):
    """
    服务日志查询上下文
    Context metadata describing the service log query
    """

    service_name: Optional[str] = Field(
        default=None,
        description="服务名称 / Target service name",
    )
    action_type: Optional[str] = Field(
        default=None,
        description="操作类型 / Filtered action type",
    )
    action_status: Optional[str] = Field(
        default=None,
        description="操作状态 / Filtered action status",
    )
    limit: int = Field(
        default=100,
        description="返回记录上限 / Maximum number of records returned",
        ge=1,
        le=1000,
    )


class ServiceLogsPayload(ServiceLogsQueryContext):
    """
    服务日志查询结果载体
    Payload containing fetched service action logs
    """

    logs: List[ServiceActionLog] = Field(
        default_factory=list,
        description="服务操作日志列表 / Collection of service action logs",
    )
    total: int = Field(
        default=0,
        description="日志数量 / Number of logs returned",
        ge=0,
    )

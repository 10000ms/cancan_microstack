from enum import StrEnum
from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.schemas.infra.push import PushResult


class ServiceConfigEntry(BaseModel):
    """
    服务配置条目数据模型
    Service configuration entry data model
    """

    key: str = Field(..., description="配置键 / Configuration key")
    value: str = Field(..., description="配置值 / Configuration value")


class ServiceConfigDetail(BaseModel):
    """
    指定服务的配置详情
    Detailed configuration values for a specific service
    """

    service_name: str = Field(..., description="服务名称 / Service name")
    items: List[ServiceConfigEntry] = Field(
        default_factory=list,
        description="配置项列表 / Collection of configuration entries",
    )


class ServiceConfigOverview(BaseModel):
    """
    所有服务的配置汇总
    Aggregated configuration overview for all services
    """

    services: List[ServiceConfigDetail] = Field(
        default_factory=list,
        description="所有服务配置详情 / Detailed configurations for each service",
    )


class ConfigPushStatus(StrEnum):
    """
    配置推送操作的状态枚举
    Status enumeration for config push execution
    """

    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"


class ConfigPushExecutionResult(BaseModel):
    """
    配置推送执行结果模型
    Config push execution result model
    """

    status: ConfigPushStatus = Field(..., description="执行状态 / Execution status")
    summary: Optional[PushResult] = Field(
        default=None,
        description="推送结果汇总 / Summary of push execution",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="错误信息 / Error message when execution failed",
    )


class ServiceConfigOperationSummary(BaseModel):
    """
    服务配置操作结果模型
    Service configuration operation result model
    """

    service_name: str = Field(..., description="服务名称 / Target service name")
    message: str = Field(..., description="操作说明 / Operation message")
    push_result: Optional[ConfigPushExecutionResult] = Field(
        default=None,
        description="配置推送执行情况 / Config push execution outcome",
    )

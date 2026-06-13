"""
Docker Compose 相关的模型

定义了与 Docker Compose 操作相关的数据模型，用于 controllersrv 的领域层。
"""
from typing import List

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.schemas.controllersrv.docker_models import ContainerHealthDetail


class CommandResult(BaseModel):
    """表示已执行的 shell 命令的结果。"""
    success: bool
    output: str = ""
    error: str = ""
    returncode: int


class ServiceListResult(BaseModel):
    """表示服务列表，用于状态和配置列表。"""
    success: bool
    services: List[str] = Field(default_factory=list)
    error: str = ""


class ContainerHealthResult(BaseModel):
    """表示服务的容器健康状态。"""
    success: bool
    containers: List[ContainerHealthDetail] = Field(default_factory=list)
    error: str = ""


class ComposeStatusResult(BaseModel):
    """表示 Docker Compose 项目的整体状态。"""
    success: bool = True
    is_running: bool
    project_name: str
    compose_file: str
    engine_type: str
    available_services: List[str] = Field(default_factory=list)
    running_services: List[str] = Field(default_factory=list)
    error: str = ""
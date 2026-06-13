from datetime import datetime
from typing import (
    Any,
    Dict,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.schemas.infra.enums import HookExecutionResult as HookResult


class HookContext(BaseModel):
    """钩子执行上下文"""
    service_name: str = Field(description="服务名称")
    service_type: str = Field(description="服务类型")
    instance_id: str = Field(description="实例ID")
    host: Optional[str] = Field(default=None, description="主机地址")
    port: Optional[int] = Field(default=None, description="端口号")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout: int = Field(default=30, description="超时时间")
    dry_run: bool = Field(default=False, description="是否为试运行")


class HookExecutionResult(BaseModel):
    """钩子执行结果"""
    hook_name: str = Field(description="钩子名称")
    result: HookResult = Field(description="执行结果")
    message: str = Field(default="", description="消息")
    execution_time: float = Field(default=0.0, description="执行时间")
    error: Optional[str] = Field(default=None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    retry_count: int = Field(default=0, description="重试次数")

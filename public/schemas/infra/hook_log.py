"""
Hook 日志数据模型
Hook logging data models
"""
from typing import (
    Dict,
    Any,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)


class HookInfo(BaseModel):
    """
    钩子信息模型
    Hook information model
    """
    name: str = Field(..., description="钩子名称 / Hook name")
    type: str = Field(..., description="钩子类型 / Hook type")
    priority: Optional[str] = Field(None, description="钩子优先级 / Hook priority")


class HookLogData(BaseModel):
    """
    钩子日志数据模型，用于结构化日志输出
    Hook log data model for structured logging
    """
    timestamp: str = Field(..., description="时间戳 (ISO格式) / Timestamp (ISO format)")
    hook: HookInfo = Field(..., description="钩子信息 / Hook information")
    message: str = Field(..., description="日志消息 / Log message")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文数据 / Context data")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）/ Execution time (seconds)")
    error: Optional[str] = Field(None, description="错误信息 / Error message")
    rejection_reason: Optional[str] = Field(None, description="拒绝原因 / Rejection reason")
    modifications: Optional[Dict[str, Any]] = Field(None, description="修改内容 / Modifications")

    class Config:
        from_attributes = True

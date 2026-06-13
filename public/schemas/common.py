"""优化后的标准 API 响应 / Optimized Standard API Response."""
from typing import (
    Generic,
    Optional,
    TypeVar,
)

from pydantic import (
    BaseModel,
    Field,
)

T = TypeVar("T")


class APIError(BaseModel):
    """API 错误信息模型 / API error information model"""
    code: str = Field(default="0", description="错误代码 / Error code")
    msg: str = Field(default="", description="错误消息 / Error message")


class APIResponse(BaseModel, Generic[T]):
    """标准 API 响应模型 / Standard API response model"""

    success: bool = Field(..., description="操作是否成功 / Whether operation succeeded")
    error: APIError = Field(default_factory=APIError, description="错误信息 / Error details")
    data: Optional[T] = Field(default=None, description="响应数据 / Response payload")

    @classmethod
    def create(
            cls,
            data: Optional[T] = None,
            code: str = "0",
            msg: str = "",
            error: Optional[APIError] = None,
            success: Optional[bool] = None,
    ) -> "APIResponse[Optional[T]]":
        """
        通用构建方法 (替代 build_api_response)
        """
        resolved_error = error or APIError(code=str(code), msg=str(msg))
        # 如果 success 未指定，根据 code 是否为 "0" 自动判断
        resolved_success = success if success is not None else resolved_error.code == "0"

        return cls(
            success=resolved_success,
            error=resolved_error,
            data=data
        )

    @classmethod
    def success_resp(cls, data: Optional[T] = None) -> "APIResponse[Optional[T]]":
        """
        快速构建成功响应 (替代 build_success_response)
        """
        return cls.create(data=data, code="0", msg="", success=True)

    @classmethod
    def error_resp(cls, code: str, msg: str) -> "APIResponse[Optional[T]]":
        """
        快速构建错误响应 (替代 build_error_response)
        """
        return cls.create(data=None, code=code, msg=msg, success=False)


class MessageResp(BaseModel):
    """
    通用消息响应
    General message response
    """
    message: str = Field(..., description="消息内容 / Message content")


class ErrorMessage(BaseModel):
    """
    错误消息模型 / Error message model
    """
    message: str = Field(..., description="错误消息 / Error message")
    detail: Optional[str] = Field(default=None, description="错误详情 / Error detail")

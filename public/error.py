"""Cancan Microstack public exceptions.

为本库代码提供统一异常类型，避免依赖业务仓库的代码。
Provide shared exceptions for the library without depending on any consumer repo.
"""

import http
from typing import Optional

from linglong_web.core.errors import LinglongHTTPException

from cancan_microstack.public.const.error import ErrorCode


class HTTPException(LinglongHTTPException):
    """HTTP 异常 / HTTP exception."""

    def __init__(
        self,
        status_code: int = http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        error_code: str = ErrorCode.SYSTEM_ERROR,
        msg: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            error_code=error_code,
            message=msg,
            detail=detail,
        )


class ParamError(HTTPException):
    """参数错误 / Invalid parameter error."""

    def __init__(self, msg: Optional[str] = None, error_code: str = ErrorCode.INVALID_PARAM) -> None:
        super().__init__(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=error_code,
            msg=msg or "Invalid request parameters",
        )

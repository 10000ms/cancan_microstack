import http
from enum import StrEnum


class ErrorCode(StrEnum):
    SUCCESS = "0"
    INVALID_PARAM = "4000"
    USER_UNLOGIN = "4001"
    HANDLER_NOT_FOUND = "4004"
    REGISTRATION_REJECTED = "4009"
    SYSTEM_ERROR = "5000"
    SERVICE_MANAGEMENT_ERROR = "5001"
    MISSING_REQUIRED_PARAM = "4002"
    NETWORK_ERROR = "5100"

    @classmethod
    def http_status_to_error_code(cls, http_status_code: int) -> str:
        d = {
            http.HTTPStatus.OK.value: cls.SUCCESS,
            http.HTTPStatus.BAD_REQUEST.value: cls.INVALID_PARAM,
            http.HTTPStatus.UNAUTHORIZED.value: cls.USER_UNLOGIN,
            http.HTTPStatus.NOT_FOUND.value: cls.HANDLER_NOT_FOUND,
            http.HTTPStatus.INTERNAL_SERVER_ERROR.value: cls.SYSTEM_ERROR,
            http.HTTPStatus.GATEWAY_TIMEOUT.value: cls.NETWORK_ERROR,
        }
        return d.get(http_status_code, cls.SUCCESS)


class ErrorMsg(StrEnum):
    SUCCESS = "success"
    COMMON_ERROR = "system error"
    INVALID_PARAM = "params error"
    USER_UNLOGIN = "user not login"
    HANDLER_NOT_FOUND = "not found"
    SERVICE_MANAGEMENT_ERROR = "service management operation failed"
    MISSING_REQUIRED_PARAM = "missing required parameter"
    NETWORK_ERROR = "network error"

    @classmethod
    def get_msg(cls, code: str | int) -> str:
        if code is None or code == "":
            return cls.SUCCESS
        if isinstance(code, int):
            code = str(code)
        d = {
            ErrorCode.SUCCESS: cls.COMMON_ERROR,
            ErrorCode.INVALID_PARAM: cls.INVALID_PARAM,
            ErrorCode.USER_UNLOGIN: cls.USER_UNLOGIN,
            ErrorCode.HANDLER_NOT_FOUND: cls.HANDLER_NOT_FOUND,
            ErrorCode.NETWORK_ERROR: cls.NETWORK_ERROR,
        }
        if code in d:
            return d[code]
        elif code.isdigit() and int(code) in http.HTTPStatus:
            return http.HTTPStatus(int(code)).phrase
        return cls.COMMON_ERROR

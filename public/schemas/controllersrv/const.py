"""
controllersrv API 常量定义
"""
from enum import Enum


class ErrorCode(str, Enum):
    """错误代码枚举"""
    SUCCESS = "0"
    INVALID_PARAMETER = "1001"
    MISSING_PARAMETER = "1002"
    INVALID_SERVICE_NAME = "1003"
    DUPLICATE_SERIAL_NUMBER = "1004"
    OPERATION_FAILED = "1005"
    SERVICE_NOT_FOUND = "1006"
    INTERNAL_ERROR = "1999"


class ValidationResultKey(str, Enum):
    """验证结果键枚举"""
    VALID = "valid"
    INVALID_SERVICES = "invalid_services"
    NON_OPERABLE_SERVICES = "non_operable_services"
    VALID_SERVICES = "valid_services"
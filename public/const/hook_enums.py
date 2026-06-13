"""
Hook-related enums.
"""
from enum import StrEnum, IntEnum


class HookResult(StrEnum):
    """钩子执行结果枚举"""
    SUCCESS = "success"           # 成功
    FAILURE = "failure"           # 失败
    SKIP = "skip"                 # 跳过
    RETRY = "retry"               # 重试
    TERMINATE = "terminate"       # 终止


class HookType(StrEnum):
    """钩子类型枚举 / Hook type enum"""
    PRE_REGISTER = "pre_register"           # 注册前钩子
    POST_REGISTER = "post_register"         # 注册后钩子
    PRE_DEREGISTER = "pre_deregister"       # 注销前钩子
    POST_DEREGISTER = "post_deregister"     # 注销后钩子


class HookPriority(IntEnum):
    """钩子优先级枚举"""
    HIGHEST = 0
    HIGH = 25
    MEDIUM = 50
    NORMAL = 50
    LOW = 75
    LOWEST = 100


class HookLogAction(StrEnum):
    """
    钩子日志行为类型枚举
    Hook log action type enum
    """
    REGISTERED = "registered"                  # 钩子已注册
    DEREGISTERED = "deregistered"              # 钩子已注销
    EXECUTION_STARTED = "execution_started"    # 执行开始
    EXECUTION_SUCCESS = "execution_success"    # 执行成功
    EXECUTION_FAILURE = "execution_failure"    # 执行失败
    REJECTION = "rejection"                    # 拒绝注册
    MODIFICATION = "modification"              # 修改服务信息


class SensitiveFieldKey(StrEnum):
    """
    敏感字段名枚举（用于日志脱敏）
    Sensitive field key enum (for log sanitization)
    """
    PASSWORD = "password"
    TOKEN = "token"
    SECRET = "secret"
    CREDENTIAL = "credential"
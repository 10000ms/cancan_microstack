"""
controllersrv API 常量定义
"""
from enum import StrEnum


class ServiceScope(StrEnum):
    """
    服务范围枚举
    """
    ALL_SERVICES = "all_services"  # 所有服务


class TimeoutKey(StrEnum):
    """
    超时配置键枚举
    """
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    PS = "ps"
    CONFIG = "config"


class DockerCommand(StrEnum):
    """
    Docker Compose 命令枚举
    """
    UP = "up"
    DOWN = "down"
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    PS = "ps"
    LOGS = "logs"
    EXEC = "exec"
    BUILD = "build"
    PULL = "pull"
    CONFIG = "config"
    VERSION = "version"


class DockerFlag(StrEnum):
    """
    Docker Compose 标志枚举
    """
    DETACHED = "-d"
    BUILD = "--build"
    FORCE_RECREATE = "--force-recreate"
    NO_RECREATE = "--no-recreate"
    REMOVE_ORPHANS = "--remove-orphans"
    QUIET = "-q"
    FORMAT = "--format"
    FILTER = "-f"
    ALL = "-a"
    NO_CACHE = "--no-cache"
    PROJECT_NAME = "-p"
    TAIL = "--tail"
    FOLLOW = "-f"
    TIMEOUT = "-t"
    FORMAT_ID = "{{.ID}}"


class ContainerCommand(StrEnum):
    """
    容器命令枚举（docker/podman 通用）
    """
    PS = "ps"
    INSPECT = "inspect"
    LOGS = "logs"
    EXEC = "exec"
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    RM = "rm"
    IMAGES = "images"
    VERSION = "version"


class ComposeCommand(StrEnum):
    """
    Compose 命令枚举
    """
    DOCKER_COMPOSE = "docker-compose"
    PODMAN_COMPOSE = "podman-compose"


class ServiceCategory(StrEnum):
    """
    服务分类枚举
    """
    INFRASTRUCTURE = "infrastructure"  # 基础设施服务（postgres, redis, pgweb, caddy）
    FRAMEWORK = "framework"  # 框架服务（infrasrv, opsbffsrv）
    BUSINESS = "business"  # 业务服务（其他所有服务）


class ValidationResultKey(StrEnum):
    """
    服务验证返回字典的键名
    """
    VALID = "valid"
    INVALID_SERVICES = "invalid_services"
    NON_OPERABLE_SERVICES = "non_operable_services"
    VALID_SERVICES = "valid_services"


class ControllersrvErrorCode(StrEnum):
    """
    controllersrv服务专用错误码
    
    注意：通用错误（如系统错误）应使用 ErrorCode（来自 public/const/error.py）
    此处仅定义 controllersrv 特有的错误码
    
    通用错误码（应使用 ErrorCode）：
    - SYSTEM_ERROR (5000): 系统内部错误
    - INVALID_PARAM (4000): 通用参数错误
    - NETWORK_ERROR (5100): 网络错误
    """
    # 参数错误 400xx (controllersrv 特有)
    INVALID_PARAMETER = "40001"         # 无效参数
    MISSING_PARAMETER = "40002"         # 缺少参数
    INVALID_SERVICE_NAME = "40003"      # 无效服务名称
    DUPLICATE_SERIAL_NUMBER = "40004"   # 流水号重复
    
    # 业务错误 500xx (controllersrv 特有)
    OPERATION_FAILED = "50001"          # 操作执行失败
    SERVICE_NOT_FOUND = "50002"         # 服务未找到
    TASK_QUEUE_FULL = "50003"           # 任务队列已满
    TASK_TIMEOUT = "50004"              # 任务执行超时
    EXECUTOR_NOT_AVAILABLE = "50005"    # 执行器不可用
    SERVICE_STATUS_ERROR = "50006"      # 获取服务状态失败
    COMPOSE_STATUS_ERROR = "50007"      # 获取 Compose 状态失败


class ControllersrvMessage(StrEnum):
    """
    controllersrv 内部使用的常量消息
    """
    DUPLICATE_SERIAL = "Duplicate"


# 基础设施服务列表（不可操作）
INFRASTRUCTURE_SERVICES = {
    "postgres",
    "postgres.internal",
    "redis",
    "redis.internal",
    "pgweb",
    "pgweb.internal",
    "caddy",
    "caddy.internal",
}

# 框架服务列表（不可操作）
FRAMEWORK_SERVICES = {
    "infrasrv",
    "infrasrv.service",
    "opsbffsrv",
    "opsbffsrv.service",
}

# 不可操作的服务集合
NON_OPERABLE_SERVICES = INFRASTRUCTURE_SERVICES | FRAMEWORK_SERVICES
import http
import re
from enum import StrEnum


class UserAgentConst(StrEnum):
    """用户代理相关常量"""
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/134.0.0.0 Safari/537.36")


class WebServerConst:
    """Web 服务器相关常量"""
    # Docker/Podman 默认不安全的主机名 / Default unsafe hostnames used by Docker/Podman
    UNSAFE_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}
    # 容器ID的正则表达式 / Regular expression for container IDs
    CONTAINER_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$")
    # 特殊服务列表，这些服务有特殊的行为 / List of special services with unique behaviors
    SPECIAL_SERVICES = ("controllersrv", "infrasrv", "opsbffsrv")


class Environment(StrEnum):
    """运行环境常量"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class LogLevelEnum(StrEnum):
    """日志等级枚举 / Log level enum."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# HTTP 方法常量集合
HTTP_METHODS = [m.value for m in http.HTTPMethod.__members__.values()]

# 支持的文件扩展名常量集合
SUPPORTED_EXTENSIONS = [".py", ".pyx", ".pyi"]

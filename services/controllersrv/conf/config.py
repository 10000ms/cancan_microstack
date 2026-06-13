import logging
import os

from linglong_web import LinglongConfigBase

from cancan_microstack.runtime.workspace import configure_workspace, ensure_server_log_dir

_WORKSPACE_ROOT = str(configure_workspace())
ensure_server_log_dir()


def _resolve_compose_file() -> str:
    """根据实际存在的文件动态选择 Compose 配置
    Select the compose file dynamically based on what exists on disk."""

    env_override = os.getenv("CANCAN_COMPOSE_FILE")
    if env_override:
        return env_override

    candidates = [
        os.path.join(_WORKSPACE_ROOT, "compose.cancan.yml"),
        os.path.join(_WORKSPACE_ROOT, "docker-compose.yml"),
        os.path.join(_WORKSPACE_ROOT, "docker-compose.services.yml"),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    # 默认返回第一个候选，哪怕文件暂时缺失
    # Default to the first candidate even if it does not exist yet
    return candidates[0]


class _BaseConfig(LinglongConfigBase):
    """controllersrv 基础配置"""

    # 特殊标识：这是一个控制器服务，不需要服务注册等逻辑
    IS_CONTROLLER_SERVICE = True

    # 禁用数据库初始化：controllersrv 不访问 PostgreSQL
    # Disable PostgreSQL initialization because controllersrv never talks to PGSQL
    PGSQL_HOST = ""
    PGSQL_USER = ""
    PGSQL_PASSWORD = ""
    PGSQL_DB = ""
    PGSQL_DATABASES = None

    # Docker Compose 配置
    DOCKER_COMPOSE_FILE = _resolve_compose_file()
    # 默认使用工作区目录名作为 project_name；可通过环境变量覆盖
    # Default to workspace folder name as project_name; override via env when needed
    DOCKER_COMPOSE_PROJECT_NAME = os.getenv("CANCAN_COMPOSE_PROJECT_NAME") or (os.path.basename(_WORKSPACE_ROOT) or "cancan")

    # controllersrv 监听端口
    CONTROLLER_PORT = 22100

    # 日志配置 - 启用文件写入（10个文件，每个10MB）
    LOGGING_ENABLE_FILE_HANDLER = True
    LOGGING_FILE_ADDR_FORMAT = os.path.join(_WORKSPACE_ROOT, "server_log_data", "controllersrv-{}.log")
    LOGGING_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOGGING_FILE_BACKUP_COUNT = 10  # 保留10个备份文件
    LOGGING_LEVEL = logging.INFO
    DEBUG = False


class _ProductionConfig(_BaseConfig):
    """生产环境配置"""
    DEBUG = False
    LOGGING_LEVEL = logging.INFO


# 必须导出 service_conf_dict
service_conf_dict = {
    'prod': _ProductionConfig,
}

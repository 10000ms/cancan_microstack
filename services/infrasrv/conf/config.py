import logging
import os

from linglong_web import LinglongConfigBase
from cancan_microstack.public.const.workflow_consts import WorkflowTask

from cancan_microstack.runtime.resources import resolve_workspace_or_asset
from cancan_microstack.runtime.workspace import configure_workspace, ensure_server_log_dir

_WORKSPACE_ROOT = str(configure_workspace())
ensure_server_log_dir()


class _BaseConfig(LinglongConfigBase):
    """基础配置"""
    DEBUG = False

    # 项目根目录（动态获取）
    _PROJECT_ROOT = _WORKSPACE_ROOT

    INFRASRV_HOST = "http://infrasrv.service:8080"
    CONTROLLERSRV_HOST = os.getenv("CONTROLLERSRV_HOST", "http://host.containers.internal:22100")

    SKIP_SERVICE_REGISTRY = True

    # DDL 自管理配置
    ENABLE_DDL_AUTO_INIT = True  # 启动时自动创建 infra 表
    # DDL 脚本路径使用项目根目录
    # - In Pod: /app/ddl/infra (Dockerfile COPY)
    # - Out Pod: {project_root}/ddl/infra
    DDL_SCRIPT_PATH = str(resolve_workspace_or_asset("ddl/infra", "ddl/infra"))

    # 数据库配置
    PGSQL_DB = "infra"  # infrasrv 使用 infra 数据库

    # PostgreSQL 连接池配置（兼顾并发与连接上限）
    # PostgreSQL pool settings (balance concurrency and connection cap)
    # 说明：infrasrv 需要同时处理操作轮询、健康检查、日志写入和服务管理写操作。
    # Note: infrasrv handles operation polling, health checks, log ingestion, and management writes concurrently.
    PGSQL_POOL_SIZE = 5
    PGSQL_MAX_OVERFLOW = 5

    # 服务注册清理配置 / Service registry cleanup settings
    INSTANCE_HEARTBEAT_TIMEOUT_SECONDS = 90  # 僵尸实例的超时阈值（秒） / Stale instance threshold (seconds)

    # 业务日志消费配置 / Business log ingestion settings
    LOG_PIPELINE_CONSUMER_ENABLED = True
    RABBITMQ_LOG_CONNECTION_NAME = "infrasrv-log-consumer"

    # RabbitMQ 连接配置（日志消费 + 工作流 broker）
    # RabbitMQ connection settings (log consumer + workflow broker)
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq.internal")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
    RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME", "admin")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "admin123")

    # MongoDB 配置（日志存储） / MongoDB settings for log storage
    # 注意：默认使用 root 用户认证数据库 admin
    # Note: default uses root user with authSource=admin
    MONGODB_URI = os.getenv(
        "MONGODB_URI",
        "mongodb://admin:admin123@mongo.internal:27017/admin?authSource=admin",
    )
    MONGODB_DB = "infra_logging"
    MONGODB_COLLECTION = "service_logs"

    # Celery 调度配置（基于 RabbitMQ + Redis）
    # Celery scheduling settings (broker via RabbitMQ, backend via Redis)
    ENABLE_WORKFLOW_CELERY = True
    CELERY_APP_NAME = "infrasrv_workflow"
    CELERY_RESULT_BACKEND_DB = 5
    CELERY_TIMEZONE = "Asia/Shanghai"
    CELERY_ENABLE_UTC = True
    CELERY_BEAT_SCHEDULE = {
        "scan-workflow-triggers": {
            "task": WorkflowTask.SCAN_SCHEDULED,
            "schedule": 5.0,
        }
    }

    # 日志配置 - 使用项目根目录
    # - In Pod: /app/server_log_data/{}.log (volume 挂载到宿主机)
    # - Out Pod: {project_root}/server_log_data/{}.log
    LOGGING_ENABLE_FILE_HANDLER = True
    LOGGING_FILE_ADDR_FORMAT = os.path.join(_PROJECT_ROOT, "server_log_data", "{}.log")


class _ProductionConfig(_BaseConfig):
    """生产环境配置"""
    ENV_MODE = "prod"
    DEBUG = False
    LOGGING_LEVEL = logging.INFO


service_conf_dict = {
    'prod': _ProductionConfig,
}

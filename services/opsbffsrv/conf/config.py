import base64
import logging
import os
from pathlib import Path

from linglong_web import LinglongConfigBase

from cancan_microstack.runtime.resources import resolve_workspace_or_asset
from cancan_microstack.runtime.workspace import configure_workspace, ensure_server_log_dir

_WORKSPACE_ROOT = str(configure_workspace())
ensure_server_log_dir()


def _build_basic_auth(username: str, password: str) -> str:
    """构建 Basic Auth 头 / Build HTTP Basic Authorization header."""

    token = base64.b64encode(f"{username}:{password}".encode("latin1")).decode("ascii")
    return f"Basic {token}"


def _resolve_compose_file(project_root: str) -> str | None:
    """Resolve docker-compose file path, preferring env overrides."""
    env_override = os.getenv("DBADMIN_COMPOSE_FILE")
    if env_override:
        return env_override

    candidates = (
        os.path.join(project_root, "docker-compose.yml"),
        os.path.join(project_root, "docker-compose.infra.yml"),
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


class _BaseConfig(LinglongConfigBase):
    """基础配置"""
    DEBUG = False

    # 项目根目录（动态获取）
    _PROJECT_ROOT = _WORKSPACE_ROOT

    # 基础设施服务地址 / Infrastructure service URL
    INFRASRV_HOST = os.getenv("INFRASRV_HOST", "http://infrasrv.service:8080")
    CONTROLLERSRV_HOST = os.getenv("CONTROLLERSRV_HOST", "http://host.containers.internal:22100")

    # opsbffsrv 不参与服务注册 / Opsbffsrv does not participate in service registry
    SKIP_SERVICE_REGISTRY = True

    # DDL 自管理配置
    ENABLE_DDL_AUTO_INIT = True  # 启动时自动创建 ops 表
    # DDL 脚本路径使用项目根目录
    # - In Pod: /app/ddl/ops (Dockerfile COPY)
    # - Out Pod: {project_root}/ddl/ops
    DDL_SCRIPT_PATH = str(resolve_workspace_or_asset("ddl/ops", "ddl/ops"))

    # 服务注册信息展示的陈旧实例剔除阈值（秒）
    # Stale instance threshold (seconds) for registry/overview views
    SERVICE_INSTANCE_STALE_SECONDS = 180

    # 数据库配置（Docker 网络地址）
    PGSQL_DB = "ops"

    # PostgreSQL 连接池配置（强制限制连接数，避免连接无限上涨）
    # PostgreSQL pool settings (hard cap connections to avoid exhaustion)
    PGSQL_POOL_SIZE = 1
    PGSQL_MAX_OVERFLOW = 0
    PGSQL_DATABASES = {
        "infra": {
            "database": "infra",
        },
        "biz": {
            "database": "biz",
        },
    }

    # 管理 UI 代理凭据 / Admin proxy credentials for proxied UIs
    # 管理 UI 代理上游地址 / Upstream base URLs for proxied UIs
    MONGO_EXPRESS_BASE_URL = os.getenv("MONGO_EXPRESS_BASE_URL", "http://mongo-express.internal:8081")
    RABBITMQ_MGMT_BASE_URL = os.getenv("RABBITMQ_MGMT_BASE_URL", "http://rabbitmq.internal:15672")
    PGWEB_BASE_URL = os.getenv("PGWEB_BASE_URL", "http://pgweb.internal:8081")
    REDIS_COMMANDER_BASE_URL = os.getenv("REDIS_COMMANDER_BASE_URL", "http://redis-commander.internal:8081")

    MONGO_EXPRESS_USERNAME = os.getenv("MONGO_EXPRESS_USERNAME", "admin")
    MONGO_EXPRESS_PASSWORD = os.getenv("MONGO_EXPRESS_PASSWORD", "admin123")
    RABBITMQ_MGMT_USERNAME = os.getenv("RABBITMQ_MGMT_USERNAME", "admin")
    RABBITMQ_MGMT_PASSWORD = os.getenv("RABBITMQ_MGMT_PASSWORD", "admin123")

    # RabbitMQ Management UI 假登录注入凭据 / Fake login credentials injected for RabbitMQ UI
    DUMMY_USER = os.getenv("RABBITMQ_MGMT_DUMMY_USER", "ops_user")
    DUMMY_PASS = os.getenv("RABBITMQ_MGMT_DUMMY_PASS", "dummy_pass")
    DUMMY_AUTH_TOKEN = os.getenv(
        "RABBITMQ_MGMT_DUMMY_AUTH_TOKEN",
        _build_basic_auth(DUMMY_USER, DUMMY_PASS),
    )

    # 日志查询 MongoDB 配置 / Mongo settings for log queries
    # 注意：默认使用 root 用户认证数据库 admin
    # Note: default uses root user with authSource=admin
    MONGODB_URI = os.getenv(
        "MONGODB_URI",
        "mongodb://admin:admin123@mongo.internal:27017/admin?authSource=admin",
    )
    MONGODB_DB = "infra_logging"
    MONGODB_COLLECTION = "service_logs"
    LOG_QUERY_MAX_RANGE_DAYS = 7  # 最大查询时间跨度（天）/ Max time range for log search (days)
    LOG_QUERY_DEFAULT_PAGE_SIZE = 100
    LOG_QUERY_MAX_PAGE_SIZE = 500

    # 数据库 schema 管理配置（opsbffsrv 在 Docker 内，可以访问 Docker Compose 服务）
    DOCKER_COMPOSE_FILE = _resolve_compose_file(_PROJECT_ROOT)
    DOCKER_COMPOSE_PROJECT_NAME = os.getenv(
        "DBADMIN_COMPOSE_PROJECT",
        os.getenv("CANCAN_STACK_PREFIX", Path(_PROJECT_ROOT).name or "cancan"),
    )
    DBADMIN_TARGET_SERVICE = "postgres.service"  # 直接访问 postgres 服务
    DBADMIN_SCRIPT_PATH = "src/tools/dbadmin/manage.py"
    DBADMIN_PYTHON_EXECUTABLE = "python"

    # 日志配置 - 使用项目根目录
    # - In Pod: /app/server_log_data/{}.log (volume 挂载到宿主机)
    # - Out Pod: {project_root}/server_log_data/{}.log
    LOGGING_ENABLE_FILE_HANDLER = True
    LOGGING_FILE_ADDR_FORMAT = os.path.join(_PROJECT_ROOT, "server_log_data", "{}.log")
    DBADMIN_PYTHONPATH = "/app/src:/app/cmd"

    # ── 认证配置 / Authentication configuration ──────────────────────────────
    AUTH_TOTP_FERNET_KEY = os.getenv("AUTH_TOTP_FERNET_KEY", "")
    AUTH_SESSION_TTL = int(os.getenv("AUTH_SESSION_TTL", "86400"))
    AUTH_TEMP_TOKEN_TTL = int(os.getenv("AUTH_TEMP_TOKEN_TTL", "300"))
    AUTH_CAPTCHA_TTL = int(os.getenv("AUTH_CAPTCHA_TTL", "60"))
    AUTH_IP_MAX_FAILURES = int(os.getenv("AUTH_IP_MAX_FAILURES", "5"))
    AUTH_IP_LOCKOUT_TTL = int(os.getenv("AUTH_IP_LOCKOUT_TTL", "1800"))
    # TOTP 单 temp_token 允许的最大失败次数（超过则失效 token）
    # Max TOTP attempts allowed per temp_token before the token is invalidated.
    AUTH_TOTP_MAX_FAILURES = int(os.getenv("AUTH_TOTP_MAX_FAILURES", "5"))
    # 生产默认 true（仅 HTTPS 下发 session cookie），可被环境变量覆盖（如本地 http 调试设 false）。
    # Default true in production (session cookie only over HTTPS); override via env (e.g. "false" for local http).
    AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "true")
    AUTH_TOTP_ISSUER = os.getenv("AUTH_TOTP_ISSUER", "OPS Admin")
    AUTH_REDIS_URL = os.getenv("AUTH_REDIS_URL", "redis://redis.service:6379/0")

    # 代理接口跨域白名单（逗号分隔的 Origin），默认空 = 仅同源。
    # 用于 RabbitMQ 等管理 UI 代理；绝不反射任意 Origin + 带凭证。
    # Allowlist of cross-origin Origins for proxy endpoints (comma-separated).
    # Empty (default) means same-origin only. Never reflect arbitrary Origin with credentials.
    PROXY_CORS_ALLOWED_ORIGINS = os.getenv("PROXY_CORS_ALLOWED_ORIGINS", "")


class _ProductionConfig(_BaseConfig):
    """生产环境配置"""
    ENV_MODE = "prod"
    DEBUG = False
    LOGGING_LEVEL = logging.INFO


service_conf_dict = {
    'prod': _ProductionConfig,
}


_logger = logging.getLogger(__name__)

# 临时生成的 Fernet key 在开发模式下会写回 LinglongConfig，
# 这里记录，避免重复生成/重复打印 warning。
# Holds the dev-mode ephemeral Fernet key so it stays stable within a process.
_dev_ephemeral_fernet_key: str | None = None


def _is_production_mode() -> bool:
    """判断是否处于生产模式 / Decide whether we are running in production.

    生产模式 = ENV_MODE 显式为 prod，或 DEBUG 关闭。
    Production = ENV_MODE explicitly "prod", or DEBUG turned off.
    """

    from linglong_web import LinglongConfig  # 延迟导入，避免启动顺序问题

    env_mode = str(getattr(LinglongConfig, "ENV_MODE", "prod")).strip().lower()
    debug = bool(getattr(LinglongConfig, "DEBUG", False))
    return env_mode == "prod" or not debug


def validate_auth_config() -> None:
    """启动期认证配置校验 / Fail-fast validation of auth-critical config.

    必须在服务启动早期调用（admin 初始化之前）。
    Must be called early during startup (before admin init / serving traffic).

    规则 / Rules:
    - 生产模式下 AUTH_TOTP_FERNET_KEY 为空 → 直接抛错，拒绝带不可用 TOTP 加密的状态上线。
    - 开发模式下为空 → 临时生成一个进程内 key 并打 warning（不持久化，重启失效）。
    """

    from cryptography.fernet import Fernet

    from linglong_web import LinglongConfig

    global _dev_ephemeral_fernet_key

    key = getattr(LinglongConfig, "AUTH_TOTP_FERNET_KEY", "")
    if key:
        return

    if _is_production_mode():
        raise RuntimeError(
            "AUTH_TOTP_FERNET_KEY is empty in production mode. "
            "TOTP secret encryption cannot run safely without it. "
            "Generate a key and set it via the AUTH_TOTP_FERNET_KEY environment variable, e.g.:\n"
            "    python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    # 开发模式：临时生成（进程内稳定，重启会变；不落盘）。
    if _dev_ephemeral_fernet_key is None:
        _dev_ephemeral_fernet_key = Fernet.generate_key().decode()
    LinglongConfig.AUTH_TOTP_FERNET_KEY = _dev_ephemeral_fernet_key
    _logger.warning(
        "AUTH_TOTP_FERNET_KEY is empty; generated an EPHEMERAL key for DEV mode only. "
        "TOTP secrets encrypted with it will NOT survive a restart. "
        "Set AUTH_TOTP_FERNET_KEY explicitly for any persistent/non-dev use."
    )

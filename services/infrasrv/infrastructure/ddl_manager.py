"""InfraSrv DDL 管理入口
InfraSrv entry point wiring the shared AutoDDLManager with service config.
"""
from pathlib import Path

from linglong_web import LinglongConfig
from linglong_web import (
    AutoDDLManager,
    DDLManagerConfig,
)

from cancan_microstack.runtime.resources import resolve_workspace_or_asset


def _build_manager() -> AutoDDLManager:
    """构建通用 DDL 管理器实例 / Build service-specific AutoDDLManager"""

    trigger_file = resolve_workspace_or_asset("ddl/trigger.sql", "ddl/trigger.sql")

    config = DDLManagerConfig(
        script_path=Path(LinglongConfig.DDL_SCRIPT_PATH),
        enable_auto_init=LinglongConfig.ENABLE_DDL_AUTO_INIT,
        trigger_sql_paths=(trigger_file,),
        required_extensions=LinglongConfig.DDL_REQUIRED_EXTENSIONS,
    )
    return AutoDDLManager(config)


async def init_ddl() -> bool:
    """初始化 DDL（供 AppServer 调用）/ Trigger schema auto-initialization"""
    return await _build_manager().check_and_init_tables()

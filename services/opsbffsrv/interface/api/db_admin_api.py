"""数据库结构管理 API 处理器 / API handlers for database schema management tasks."""
from typing import Optional

from linglong_web import build_success_response

from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.opsbffsrv.db_admin import (
    SchemaApplyRequest,
    SchemaDiffRequest,
    SchemaOperationResponse,
    SchemaRebuildDatabaseRequest,
    SchemaRebuildTablesRequest,
)
from cancan_microstack.services.opsbffsrv.application.db_admin_app import DatabaseAdminApp

# 应用层实例（懒加载）/ Lazily instantiated application layer
_db_admin_app: Optional[DatabaseAdminApp] = None


def _get_app() -> DatabaseAdminApp:
    """获取数据库管理应用层实例 / Retrieve the database admin application instance."""

    global _db_admin_app
    if _db_admin_app is None:
        _db_admin_app = DatabaseAdminApp()
    return _db_admin_app


async def schema_apply_handler(
        payload: SchemaApplyRequest,
) -> APIResponse[SchemaOperationResponse]:
    """执行模式应用操作 / Apply canonical schema definitions."""

    result = await _get_app().ensure_schema(payload)
    return build_success_response(data=result)


async def schema_diff_handler(
        payload: SchemaDiffRequest,
) -> APIResponse[SchemaOperationResponse]:
    """执行模式比对操作 / Inspect schema drift without applying changes."""

    result = await _get_app().diff_schema(payload)
    return build_success_response(data=result)


async def schema_rebuild_database_handler(
        payload: SchemaRebuildDatabaseRequest,
) -> APIResponse[SchemaOperationResponse]:
    """重建整个数据库 / Rebuild an entire database."""

    result = await _get_app().rebuild_database(payload)
    return build_success_response(data=result)


async def schema_rebuild_tables_handler(
        payload: SchemaRebuildTablesRequest,
) -> APIResponse[SchemaOperationResponse]:
    """重建指定数据表 / Rebuild selected tables."""

    result = await _get_app().rebuild_tables(payload)
    return build_success_response(data=result)

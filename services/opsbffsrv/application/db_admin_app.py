"""数据库结构管理的应用层调度器 / Application layer orchestrating schema administration commands."""
import asyncio
from typing import (
    Mapping,
    Optional,
)

from pydantic import ValidationError

from cancan_microstack.public.schemas.opsbffsrv.db_admin import (
    SchemaApplyRequest,
    SchemaDiffRequest,
    SchemaOperationResponse,
    SchemaRebuildDatabaseRequest,
    SchemaRebuildTablesRequest,
)
from linglong_web import LinglongConfig
from cancan_microstack.services.opsbffsrv.domain.db_admin.db_admin_domain import DatabaseAdminDomain
from linglong_web.utils import logger


class DatabaseAdminApp:
    """数据库结构管理应用层 / Application layer for database schema management tasks."""

    def __init__(self) -> None:
        compose_file = getattr(LinglongConfig, "DOCKER_COMPOSE_FILE", None)
        project_name = getattr(LinglongConfig, "DOCKER_COMPOSE_PROJECT_NAME", None)
        self._domain: Optional[DatabaseAdminDomain]

        if compose_file and project_name:
            self._domain = DatabaseAdminDomain(
                compose_file=compose_file,
                project_name=project_name,
                target_service=getattr(LinglongConfig, "DBADMIN_TARGET_SERVICE", "postgres.service"),
                script_path=getattr(LinglongConfig, "DBADMIN_SCRIPT_PATH", "src/tools/dbadmin/manage.py"),
                python_executable=getattr(LinglongConfig, "DBADMIN_PYTHON_EXECUTABLE", "python"),
                python_path=getattr(LinglongConfig, "DBADMIN_PYTHONPATH", None),
            )
        else:
            self._domain = None
            # 诚实说明：即便补齐 compose 配置，schema 管理仍依赖一个**未随本包分发**的外部
            # dbadmin 工具（src/tools/dbadmin/manage.py，通过 docker-compose exec 在目标容器内执行）。
            # 缺少 compose 元数据时本能力直接禁用，属设计性不可用，并非配置 bug。
            logger.warning(
                "DB schema 管理能力不可用：缺少 docker-compose 元数据，且 schema diff/apply/rebuild 依赖一个"
                " 未随本包发布的外部 dbadmin 工具（src/tools/dbadmin/manage.py）。当前部署无法提供该能力。"
                " / DB schema management disabled: missing docker-compose metadata, and it relies on an external"
                " dbadmin tool (src/tools/dbadmin/manage.py) that is NOT distributed with this package.",
            )

    def _require_domain(self) -> DatabaseAdminDomain:
        if not self._domain:
            raise RuntimeError(
                "DB schema 管理能力在当前部署中不可用（设计性不可用，非 bug）：schema diff/apply/rebuild 依赖一个"
                " 未随本包分发的外部 dbadmin 工具（src/tools/dbadmin/manage.py），需通过 docker-compose exec 在目标"
                " 容器内运行；本包既未内置该脚本，也未提供 DOCKER_COMPOSE_FILE/DOCKER_COMPOSE_PROJECT_NAME 配置。"
                " / Database schema management is unavailable in this deployment by design (not a bug): it depends on"
                " an external dbadmin tool (src/tools/dbadmin/manage.py) that is not shipped with this package."
            )
        return self._domain

    def _parse_response(self, payload: Mapping[str, object]) -> SchemaOperationResponse:
        """解析 dbadmin 输出为结构化响应 / Parse raw dbadmin payload into structured response."""

        try:
            return SchemaOperationResponse.from_cli_payload(payload)
        except ValidationError as exc:
            logger.error("Invalid dbadmin payload: %s", exc, exc_info=True)
            raise RuntimeError("Invalid dbadmin payload structure") from exc

    async def ensure_schema(self, request: SchemaApplyRequest) -> SchemaOperationResponse:
        domain = self._require_domain()
        raw = await asyncio.to_thread(
            domain.ensure_schema,
            databases=request.databases,
            tables=request.tables,
            dry_run=request.dry_run,
        )
        return self._parse_response(raw)

    async def diff_schema(self, request: SchemaDiffRequest) -> SchemaOperationResponse:
        domain = self._require_domain()
        raw = await asyncio.to_thread(
            domain.diff_schema,
            databases=request.databases,
            tables=request.tables,
        )
        return self._parse_response(raw)

    async def rebuild_database(self, request: SchemaRebuildDatabaseRequest) -> SchemaOperationResponse:
        domain = self._require_domain()
        raw = await asyncio.to_thread(domain.rebuild_database, request.database)
        return self._parse_response(raw)

    async def rebuild_tables(self, request: SchemaRebuildTablesRequest) -> SchemaOperationResponse:
        domain = self._require_domain()
        raw = await asyncio.to_thread(
            domain.rebuild_tables,
            request.database,
            request.tables,
            request.cascade,
        )
        return self._parse_response(raw)

"""Domain logic for delegating schema management to the dbadmin CLI."""
import json
import subprocess
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
)

from linglong_web.utils import logger


class DatabaseAdminDomain:
    """Execute dbadmin CLI commands inside the target service container.

    诚实声明 / Honesty note:
    本类不自带 schema 管理实现，而是通过 `docker-compose exec ... python src/tools/dbadmin/manage.py`
    外壳调用一个**未随本包分发**的外部 dbadmin 工具。该脚本不在本仓库/本包内，只有目标容器镜像里存在
    时才可用。若目标容器没有该脚本，调用会失败——这是设计性的外部依赖，并非本包内已实现的能力。
    This class shells out to an external dbadmin tool (src/tools/dbadmin/manage.py) that is NOT shipped
    with this package; it only works when that script exists inside the target container image.
    """

    def __init__(
            self,
            *,
            compose_file: str,
            project_name: str,
            target_service: str,
            script_path: str,
            python_executable: str = "python",
            python_path: str = "/app/src:/app:/app/cmd:/app/tools",
    ) -> None:
        self.compose_file = compose_file
        self.project_name = project_name
        self.target_service = target_service
        self.script_path = script_path
        self.python_executable = python_executable
        self.python_path = python_path
        self.base_compose_cmd = [
            "docker-compose",
            "-f",
            compose_file,
            "-p",
            project_name,
        ]

    def ensure_schema(self, *, databases: Optional[Sequence[str]], tables: Optional[Sequence[str]], dry_run: bool) -> \
    Dict[str, Any]:
        args = ["apply"]
        if databases:
            args.append("--databases")
            args.extend(databases)
        if tables:
            args.append("--tables")
            args.extend(tables)
        if dry_run:
            args.append("--dry-run")
        return self._run_dbadmin(args)

    def diff_schema(self, *, databases: Optional[Sequence[str]], tables: Optional[Sequence[str]]) -> Dict[str, Any]:
        args = ["diff"]
        if databases:
            args.append("--databases")
            args.extend(databases)
        if tables:
            args.append("--tables")
            args.extend(tables)
        return self._run_dbadmin(args)

    def rebuild_database(self, database: str) -> Dict[str, Any]:
        return self._run_dbadmin(["rebuild-db", database])

    def rebuild_tables(self, database: str, tables: Sequence[str], cascade: bool) -> Dict[str, Any]:
        args = ["rebuild-table", database]
        args.extend(tables)
        if not cascade:
            args.append("--no-cascade")
        return self._run_dbadmin(args)

    def _run_dbadmin(self, additional_args: List[str]) -> Dict[str, Any]:
        cmd = self.base_compose_cmd + [
            "exec",
            "-T",
            self.target_service,
            "env",
            f"PYTHONPATH={self.python_path}",
            self.python_executable,
            self.script_path,
            "--output",
            "json",
        ]
        cmd.extend(additional_args)

        logger.info("Executing dbadmin command: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            message = stderr or stdout or "dbadmin command failed"
            logger.error("dbadmin command failed: %s", message)
            raise RuntimeError(message)

        payload_text = result.stdout.strip() or result.stderr.strip()
        if not payload_text:
            logger.error("dbadmin command returned empty output")
            raise RuntimeError("dbadmin command returned empty output")

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            logger.error("Unable to parse dbadmin output: %s", payload_text)
            raise RuntimeError("dbadmin command produced invalid JSON") from exc

        return payload

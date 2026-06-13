"""Caddy access log ingestion background service.

持续读取 Caddy JSON 访问日志文件并写入数据库，供统计页面聚合。
Continuously tail Caddy JSON access logs and ingest into DB for stats dashboards.
"""

import asyncio
import os
from pathlib import Path
from typing import List

from linglong_web.utils import logger

from cancan_microstack.services.opsbffsrv.application.caddy.access_log_analysis_app import AccessLogAnalysisApp


class CaddyAccessLogIngestionService:
    """Caddy 访问日志采集后台服务 / Background ingestion service for Caddy access logs."""

    def __init__(self):
        log_path = os.getenv("CADDY_ACCESS_LOG_PATH", "/app/builds/caddy/logs/http-access.json")
        offset_path = os.getenv("CADDY_ACCESS_LOG_OFFSET_PATH", "/app/server_log_data/caddy_access_log.offset")
        poll_interval = os.getenv("CADDY_ACCESS_LOG_POLL_INTERVAL_SECONDS", "2")
        batch_size = os.getenv("CADDY_ACCESS_LOG_BATCH_SIZE", "500")

        self.log_file_path = Path(log_path)
        self.offset_file_path = Path(offset_path)
        self.poll_interval_seconds = max(float(poll_interval), 0.5)
        self.batch_size = max(int(batch_size), 1)

        self._app = AccessLogAnalysisApp()
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._missing_file_warned = False

    async def start(self) -> None:
        """启动采集任务 / Start ingestion loop."""
        if self._task and not self._task.done():
            logger.info("Caddy access log ingestion service is already running")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="caddy-access-log-ingestion")
        logger.info(
            "Caddy access log ingestion started: file=%s, offset=%s, interval=%ss, batch=%s",
            self.log_file_path,
            self.offset_file_path,
            self.poll_interval_seconds,
            self.batch_size,
        )

    async def shutdown(self) -> None:
        """停止采集任务 / Stop ingestion loop."""
        if not self._task:
            return

        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except asyncio.TimeoutError:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        finally:
            self._task = None

        logger.info("Caddy access log ingestion stopped")

    async def _run_loop(self) -> None:
        """采集主循环 / Main polling loop."""
        while not self._stop_event.is_set():
            try:
                await self.sync_once()
            except Exception as exc:
                logger.error("Caddy access log ingestion cycle failed: %s", exc, exc_info=True)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def sync_once(self) -> int:
        """执行一次增量同步 / Run one incremental ingestion cycle."""
        if not self.log_file_path.exists():
            if not self._missing_file_warned:
                logger.warning("Caddy access log file not found: %s", self.log_file_path)
                self._missing_file_warned = True
            return 0

        self._missing_file_warned = False

        current_size = self.log_file_path.stat().st_size
        offset = self._read_offset()

        # 文件被轮转或截断时回到开头 / Reset offset when file is rotated/truncated
        if offset < 0 or offset > current_size:
            offset = 0
            self._write_offset(offset)

        total_ingested = 0
        with self.log_file_path.open("r", encoding="utf-8", errors="ignore") as log_file:
            log_file.seek(offset)

            while True:
                lines, next_offset = self._read_line_batch(log_file)
                if not lines:
                    break

                result = await self._app.ingest_batch_logs(lines)
                if result.get("status") != "success":
                    logger.warning("Caddy access log ingest batch failed: %s", result)
                    break

                ingested_count = int(result.get("count", 0))
                total_ingested += ingested_count
                self._write_offset(next_offset)

        if total_ingested > 0:
            logger.info("Caddy access log ingestion synced %s entries", total_ingested)

        return total_ingested

    def _read_line_batch(self, log_file) -> tuple[List[str], int]:
        """读取一批日志行并返回读取后 offset / Read one batch and return next offset."""
        lines: List[str] = []

        for _ in range(self.batch_size):
            raw_line = log_file.readline()
            if not raw_line:
                break

            line = raw_line.strip()
            if line:
                lines.append(line)

        return lines, log_file.tell()

    def _read_offset(self) -> int:
        """读取 offset 文件 / Read persisted file offset."""
        if not self.offset_file_path.exists():
            return 0

        try:
            raw = self.offset_file_path.read_text(encoding="utf-8").strip()
            return int(raw) if raw else 0
        except Exception as exc:
            logger.warning("Failed to read caddy log offset file: %s", exc)
            return 0

    def _write_offset(self, offset: int) -> None:
        """写入 offset 文件 / Persist file offset."""
        try:
            self.offset_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.offset_file_path.write_text(str(offset), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to write caddy log offset file: %s", exc)


_ingestion_service: CaddyAccessLogIngestionService | None = None


def get_caddy_access_log_ingestion_service() -> CaddyAccessLogIngestionService:
    """获取全局采集服务实例 / Get singleton ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = CaddyAccessLogIngestionService()
    return _ingestion_service

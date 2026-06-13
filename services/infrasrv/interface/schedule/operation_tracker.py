"""定时同步 controllersrv 任务状态 / Periodic controllersrv task synchronisation"""
import asyncio

from linglong_web.utils import logger

from cancan_microstack.services.infrasrv.application.service_operation_tracker import (
    ServiceOperationTrackerApp,
)

_tracker_app = ServiceOperationTrackerApp()
_poll_lock = asyncio.Lock()


async def operation_tracker_task() -> None:
    """每次执行时轮询 controllersrv 并刷新操作状态 / Poll controllersrv and refresh operation states"""

    if _poll_lock.locked():
        logger.warning("Operation tracker still running, skipping this tick")
        return

    async with _poll_lock:
        try:
            await _tracker_app.run_once()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Operation tracker failed: %s", exc, exc_info=True)

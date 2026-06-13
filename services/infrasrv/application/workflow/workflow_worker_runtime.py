"""Embedded Celery worker runtime for infrasrv workflow tasks.

在单实例 infrasrv 内启动/停止 Celery worker，避免额外容器或进程。
The worker runs inside a dedicated daemon thread so the service can keep a
single deployment unit while still benefiting from Celery's queue semantics.
"""
import os
import threading
from typing import Optional

from celery import Celery

from linglong_web import LinglongConfig
from linglong_web import Rmanager
from linglong_web.utils import logger

_worker_thread: Optional[threading.Thread] = None
_worker_hostname: Optional[str] = None
_worker_shutdown_lock = threading.Lock()


def _build_worker_hostname() -> str:
    suffix = LinglongConfig.CELERY_WORKER_HOSTNAME_SUFFIX
    base = (
            os.environ.get("SERVICE_WORKER_HOSTNAME")
            or os.environ.get("HOSTNAME")
            or "infrasrv"
    )
    base = base.replace("/", "").split(".")[0]
    suffix = suffix.lstrip(".@") or "inline"
    return f"{base}@{suffix}"


def _build_worker_argv(hostname: str) -> list[str]:
    log_level = LinglongConfig.CELERY_WORKER_LOG_LEVEL
    concurrency = LinglongConfig.CELERY_WORKER_CONCURRENCY
    pool = LinglongConfig.CELERY_WORKER_POOL
    enable_beat = LinglongConfig.CELERY_WORKER_ENABLE_BEAT

    argv = [
        "worker",
        f"--hostname={hostname}",
        f"--loglevel={log_level}",
        "--concurrency",
        str(concurrency),
    ]

    if pool:
        argv.extend(["--pool", str(pool)])

    if enable_beat:
        argv.append("--beat")

    return argv


def start_inline_worker() -> None:
    """启动内嵌 Celery worker / Start embedded Celery worker."""

    if not LinglongConfig.CELERY_WORKER_AUTOSTART:
        logger.info("Embedded Celery worker autostart disabled via config")
        return

    app: Celery | None = Rmanager.CeleryApp
    if not app:
        logger.warning("Celery is not initialized; embedded worker skipped")
        return

    global _worker_thread, _worker_hostname
    with _worker_shutdown_lock:
        if _worker_thread and _worker_thread.is_alive():
            logger.info("Embedded Celery worker already running: hostname=%s", _worker_hostname)
            return

        hostname = _build_worker_hostname()
        argv = _build_worker_argv(hostname)

        def _run_worker():
            logger.info(
                "Starting embedded Celery worker hostname=%s argv=%s",
                hostname,
                " ".join(argv),
            )
            try:
                app.worker_main(argv=argv)
            except SystemExit as exc:
                logger.info("Embedded Celery worker exited: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.error("Embedded Celery worker crashed: %s", exc, exc_info=True)
            finally:
                logger.info("Embedded Celery worker stopped")

        worker_thread = threading.Thread(target=_run_worker, name="embedded-celery-worker", daemon=True)
        worker_thread.start()
        _worker_thread = worker_thread
        _worker_hostname = hostname


def stop_inline_worker(timeout: float = 30.0) -> None:
    """停止内嵌 Celery worker / Stop embedded Celery worker."""

    global _worker_thread
    with _worker_shutdown_lock:
        thread = _worker_thread
        if not thread or not thread.is_alive():
            _worker_thread = None
            return

        app: Celery | None = Rmanager.CeleryApp
        if app and _worker_hostname:
            try:
                logger.info("Sending shutdown signal to embedded Celery worker: %s", _worker_hostname)
                app.control.shutdown(destination=[_worker_hostname])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send shutdown command to worker: %s", exc)

        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning("Embedded Celery worker did not stop within %.1fs", timeout)
        else:
            logger.info("Embedded Celery worker terminated cleanly")
        _worker_thread = None

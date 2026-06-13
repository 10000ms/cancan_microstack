"""日志清理定时任务 / Scheduled task for log retention."""
from datetime import datetime, timedelta, timezone

from linglong_web import LinglongConfig
from linglong_web.utils import logger

from cancan_microstack.services.infrasrv.application.logging.log_ingestion_service import get_log_ingestion_service


async def cleanup_expired_logs_task() -> None:
    """删除超过保留期的日志 / Delete logs that exceed retention."""
    # 从运行时配置读取日志保留策略，提供安全默认值。
    # Read retention policy from runtime config with safe defaults.
    retention_days = int(LinglongConfig.LOG_RETENTION_DAYS)
    batch_limit = int(LinglongConfig.LOG_RETENTION_BATCH_LIMIT)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    repo = get_log_ingestion_service().get_repository()
    if repo is None:
        logger.warning("Log repository not available, skipping cleanup task")
        return

    deleted = await repo.cleanup_older_than(cutoff, batch_limit)
    logger.info(
        "Log retention cleanup finished: deleted=%s cutoff=%s", deleted, cutoff.isoformat()
    )

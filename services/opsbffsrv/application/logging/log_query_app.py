"""应用层：日志查询 / Application layer for log search."""
from typing import Optional

from linglong_web import LinglongConfig
from cancan_microstack.public.schemas.logging.log_event import (
    LogQueryRequest,
    LogQueryResponse,
)

from cancan_microstack.services.opsbffsrv.domain.logging.log_query_domain import LogQueryDomain
from cancan_microstack.services.opsbffsrv.infrastructure.mongo.log_query_repository import LogQueryRepository


class LogQueryApp:
    """调度日志查询流程 / Orchestrates log query workflows."""

    def __init__(self) -> None:
        self._repository = LogQueryRepository()
        self._domain = LogQueryDomain(self._repository)
        # 注意：该模块可能会在 LinglongConfig 初始化前被 import。
        # Note: This module may be imported before LinglongConfig is initialized.
        self._max_range_days = int(getattr(LinglongConfig, "LOG_QUERY_MAX_RANGE_DAYS", 7))

    async def search_logs(self, payload: LogQueryRequest) -> LogQueryResponse:
        return await self._domain.search_logs(payload, self._max_range_days)


log_query_app = LogQueryApp()

"""服务行为日志应用层 / Application layer for service action logs."""

from typing import (
    List,
    Optional,
)

from linglong_web.utils import logger
from cancan_microstack.public.schemas.infra.service_action_log import ServiceActionLog
from cancan_microstack.public.schemas.opsbffsrv.service_logs import ServiceLogsPayload
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.service_action_log_op import (
    get_service_action_logs,
)


class ServiceLogsApp:
    """服务日志应用层：直接访问数据库，避免链路依赖 / Fetch logs directly from infra DB."""

    @staticmethod
    def _build_service_name_variants(service_name: str) -> List[str]:
        """构建 service_name 及其变体，适配 *.service 命名风格 / Normalize service names."""
        raw = service_name.strip()
        if not raw:
            return []
        candidates = {raw}
        suffix = '.service'
        if raw.endswith(suffix):
            base = raw[:-len(suffix)]
            if base:
                candidates.add(base)
        else:
            candidates.add(f"{raw}{suffix}")
        return sorted(candidates)

    async def get_service_logs(
            self,
            service_name: Optional[str] = None,
            action_type: Optional[str] = None,
            action_status: Optional[str] = None,
            limit: int = 100,
    ) -> ServiceLogsPayload:
        """
        查询服务行为日志（直连 DB）
        Fetch service action logs directly from the infra database.
        """

        logger.info(
            "ServiceLogsApp: querying logs - service_name=%s, action_type=%s, action_status=%s, limit=%s",
            service_name,
            action_type,
            action_status,
            limit,
        )

        name_variants = self._build_service_name_variants(service_name) if service_name else None
        if name_variants:
            logger.info("Normalized service name variants: input=%s, variants=%s", service_name, name_variants)

        logs: List[ServiceActionLog] = await get_service_action_logs(
            service_name_variants=name_variants,
            action_type=action_type,
            action_status=action_status,
            limit=limit,
        )
        logger.info("Fetched %s logs from infra database", len(logs))

        return ServiceLogsPayload(
            service_name=service_name,
            action_type=action_type,
            action_status=action_status,
            limit=limit,
            logs=logs,
            total=len(logs),
        )

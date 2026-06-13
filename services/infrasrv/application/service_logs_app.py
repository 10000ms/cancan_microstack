"""
服务行为日志应用层 - 查询服务操作历史
"""

from typing import (
    List,
    Optional,
)

from linglong_web.utils import logger
from cancan_microstack.public.schemas.infra.service_action_log import ServiceActionLog
from cancan_microstack.services.infrasrv.domain.service_logs.service_logs_domain import ServiceLogsDomain


class ServiceLogsApp:
    """服务日志应用层：编排日志查询业务流程"""

    def __init__(self):
        self.domain = ServiceLogsDomain()

    async def query_logs(
            self,
            service_name: Optional[str] = None,
            action_type: Optional[str] = None,
            action_status: Optional[str] = None,
            limit: int = 100
    ) -> List[ServiceActionLog]:
        """
        查询服务行为日志
        
        Args:
            service_name: 服务名称（可选）
            action_type: 操作类型（可选）
            action_status: 操作状态（可选）
            limit: 返回数量限制
        
        Returns:
            服务行为日志列表
        """
        logger.info(
            f"ServiceLogsApp: querying logs - service_name={service_name}, "
            f"action_type={action_type}, action_status={action_status}, limit={limit}"
        )

        logs = await self.domain.get_service_action_logs(
            service_name=service_name,
            action_type=action_type,
            action_status=action_status,
            limit=limit
        )

        logger.info(f"ServiceLogsApp: found {len(logs)} logs")
        return logs

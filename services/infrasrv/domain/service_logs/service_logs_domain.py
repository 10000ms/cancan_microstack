"""
服务行为日志领域层
"""
from typing import (
    List,
    Optional,
)

from linglong_web.utils import logger
from cancan_microstack.public.schemas.infra.service_action_log import ServiceActionLog
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_action_log_op import (
    query_service_action_logs,
)


class ServiceLogsDomain:
    """服务日志领域层：处理日志查询业务逻辑"""

    async def get_service_action_logs(
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
            f"ServiceLogsDomain: querying logs - service_name={service_name}, "
            f"action_type={action_type}, action_status={action_status}, limit={limit}"
        )

        # 调用基础设施层查询数据
        logs = await query_service_action_logs(
            service_name=service_name,
            action_type=action_type,
            action_status=action_status,
            limit=limit
        )

        return logs

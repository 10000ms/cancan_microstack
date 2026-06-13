"""
健康检查应用层

封装健康检查业务流程
"""
from cancan_microstack.services.infrasrv.domain.health_check.health_check_domain import HealthCheckDomain
from cancan_microstack.public.schemas.infra.health_check import HealthCheckSummary


class HealthCheckApp:
    """健康检查应用层"""

    def __init__(self):
        """初始化应用层"""
        self.domain = HealthCheckDomain()

    async def check_all_instances(self) -> HealthCheckSummary:
        """
        检查所有实例的健康状态

        Returns:
            HealthCheckSummary: 健康检查结果汇总模型
        """
        return await self.domain.health_check_all_instances()

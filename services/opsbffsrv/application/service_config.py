"""
服务配置管理应用层
Service configuration application layer coordinating persistence and push triggers
"""
from typing import Dict

from pydantic import ValidationError

from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from linglong_web import LinglongConfig
from linglong_web.utils import logger

from cancan_microstack.services.opsbffsrv.domain.service_config.service_config import ServiceConfigDomain
from cancan_microstack.public.schemas.opsbffsrv.service_config import (
    ConfigPushExecutionResult,
    ConfigPushStatus,
    ServiceConfigDetail,
    ServiceConfigEntry,
    ServiceConfigOperationSummary,
    ServiceConfigOverview,
)
from cancan_microstack.public.schemas.infra.push import PushResult


class ServiceConfigApp:
    def __init__(self):
        self.service_config_domain = ServiceConfigDomain()

    async def get_service_config(self, service_name: str) -> ServiceConfigDetail:
        """
        获取指定服务的配置字典
        Retrieve configuration entries for a specific service
        """
        config_items = await self.service_config_domain.get_service_config(service_name)
        entries = [
            ServiceConfigEntry(key=key, value=value)
            for key, value in sorted(config_items.items())
        ]
        return ServiceConfigDetail(service_name=service_name, items=entries)

    async def insert_service_config(self, service_name: str,
                                    conf_dict: Dict[str, str]) -> ServiceConfigOperationSummary:
        """
        插入服务配置并触发推送
        Insert configuration values and trigger downstream push
        """
        await self.service_config_domain.insert_service_config(service_name, conf_dict)
        push_result = await self._trigger_config_push(service_name)
        return ServiceConfigOperationSummary(
            service_name=service_name,
            message="Config inserted successfully",
            push_result=push_result,
        )

    async def update_service_config(self, service_name: str,
                                    conf_dict: Dict[str, str]) -> ServiceConfigOperationSummary:
        """
        更新服务配置并触发推送
        Update configuration values and trigger downstream push
        """
        await self.service_config_domain.update_service_config(service_name, conf_dict)
        push_result = await self._trigger_config_push(service_name)
        return ServiceConfigOperationSummary(
            service_name=service_name,
            message="Config updated successfully",
            push_result=push_result,
        )

    async def get_all_service_configs(self) -> ServiceConfigOverview:
        """
        获取全部服务的配置概览
        Retrieve configuration overview for every registered service
        """
        all_configs = await self.service_config_domain.get_all_service_configs()
        details = [
            ServiceConfigDetail(
                service_name=service,
                items=[
                    ServiceConfigEntry(key=key, value=value)
                    for key, value in sorted(config.items())
                ],
            )
            for service, config in sorted(all_configs.items())
        ]
        return ServiceConfigOverview(services=details)

    async def delete_service_config(self, service_name: str, conf_key: str) -> ServiceConfigOperationSummary:
        """
        删除服务配置项并触发推送
        Delete configuration entry and trigger downstream push
        """
        await self.service_config_domain.delete_service_config(service_name, conf_key)
        push_result = await self._trigger_config_push(service_name)
        return ServiceConfigOperationSummary(
            service_name=service_name,
            message="Config deleted successfully",
            push_result=push_result,
        )

    async def _trigger_config_push(self, service_name: str) -> ConfigPushExecutionResult:
        """
        调用 infrasrv 的内部接口触发配置推送
        Invoke infrasrv internal API to push configuration updates
        """
        try:
            url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/internal/config/push"
            logger.info(f"Triggering config push for service: {service_name}")

            resp = await http_client.post(
                url,
                params={"service_name": service_name},
                json={"service_name": service_name},
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT,
            )

            if resp and resp.status == 200:
                data = await resp.json()
                logger.info(f"Config push triggered successfully for {service_name}")
                push_data = data.get("data") if isinstance(data, dict) else None
                push_summary = None
                if isinstance(push_data, dict):
                    try:
                        push_summary = PushResult.model_validate(push_data)
                    except ValidationError as exc:
                        logger.warning(
                            "Failed to parse push result for %s: %s",
                            service_name,
                            exc,
                        )
                return ConfigPushExecutionResult(
                    status=ConfigPushStatus.SUCCESS,
                    summary=push_summary,
                )

            http_status = resp.status if resp else "None"
            logger.warning(
                "Failed to trigger config push for %s: status %s",
                service_name,
                http_status,
            )
            return ConfigPushExecutionResult(
                status=ConfigPushStatus.FAILED,
                error_message=f"HTTP {http_status}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error triggering config push for %s: %s",
                service_name,
                exc,
                exc_info=True,
            )
            return ConfigPushExecutionResult(
                status=ConfigPushStatus.ERROR,
                error_message=str(exc),
            )

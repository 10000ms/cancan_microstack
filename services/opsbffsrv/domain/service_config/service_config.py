"""
服务配置管理领域层
负责处理ops前端对配置的管理操作
"""
from typing import Dict

from linglong_web.utils import logger
from cancan_microstack.public.schemas.infra.service_config import ServiceConfig
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.service_config import (
    insert_service_config,
    get_service_config,
    update_service_config,
    get_all_service_configs,
    delete_service_config,
)


class ServiceConfigDomain:
    """服务配置管理域"""

    async def get_service_config(self, service_name: str) -> Dict[str, str]:
        """获取服务配置"""
        configs = await get_service_config(service_name)
        if not configs:
            return {}

        config_dict = {c.conf_key: c.conf_value for c in configs}
        logger.info(f"Retrieved config for service {service_name}: {len(config_dict)} items")
        return config_dict

    async def insert_service_config(self, service_name: str, conf_dict: Dict[str, str]) -> None:
        """插入服务配置"""
        logger.info(f"Inserting config for service {service_name}: {list(conf_dict.keys())}")

        configs = [
            ServiceConfig(
                service_name=service_name,
                conf_key=key,
                conf_value=value
            )
            for key, value in conf_dict.items()
        ]

        await insert_service_config(configs)
        logger.info(f"Successfully inserted {len(configs)} config items for service {service_name}")

    async def update_service_config(self, service_name: str, conf_dict: Dict[str, str]) -> None:
        """更新服务配置"""
        logger.info(f"Updating config for service {service_name}: {list(conf_dict.keys())}")

        configs = [
            ServiceConfig(
                service_name=service_name,
                conf_key=key,
                conf_value=value
            )
            for key, value in conf_dict.items()
        ]

        await update_service_config(configs)
        logger.info(f"Successfully updated {len(configs)} config items for service {service_name}")

    async def get_all_service_configs(self) -> Dict[str, Dict[str, str]]:
        """获取所有服务的配置"""
        configs = await get_all_service_configs()

        # 按服务名分组
        service_configs: Dict[str, Dict[str, str]] = {}
        for config in configs:
            if config.service_name not in service_configs:
                service_configs[config.service_name] = {}
            service_configs[config.service_name][config.conf_key] = config.conf_value

        logger.info(f"Retrieved configs for {len(service_configs)} services")
        return service_configs

    async def delete_service_config(self, service_name: str, conf_key: str) -> None:
        """删除服务配置项"""
        logger.info(f"Deleting config for service {service_name}, key: {conf_key}")
        await delete_service_config(service_name, conf_key)
        logger.info(f"Successfully deleted config item {conf_key} for service {service_name}")

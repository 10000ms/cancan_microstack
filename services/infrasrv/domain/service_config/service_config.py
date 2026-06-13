from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_config import (
    insert_service_config,
    get_service_config,
    update_service_config,
    get_all_service_configs as db_get_all_service_configs,
    delete_service_config as db_delete_service_config,
)
from cancan_microstack.public.schemas.infra.service_config import ServiceConfig as ServiceConfigSchema


class ServiceConfig:

    async def get_service_config(self, service_name: str) -> dict:
        confs = await get_service_config(service_name)
        if not confs:
            return {}
        return {c.conf_key: c.conf_value for c in confs}

    async def insert_service_config(self, service_name: str, conf_dict: dict) -> None:
        confs = [ServiceConfigSchema(
            service_name=service_name,
            conf_key=k,
            conf_value=v
        ) for k, v in conf_dict.items()]
        await insert_service_config(confs)

    async def update_service_config(self, service_name: str, conf_dict: dict) -> None:
        confs = [ServiceConfigSchema(
            service_name=service_name,
            conf_key=k,
            conf_value=v
        ) for k, v in conf_dict.items()]
        await update_service_config(confs)

    async def get_all_service_configs(self) -> dict:
        """获取所有服务的配置"""
        all_confs = await db_get_all_service_configs()

        # 按服务名分组
        result = {}
        for conf in all_confs:
            if conf.service_name not in result:
                result[conf.service_name] = {}
            result[conf.service_name][conf.conf_key] = conf.conf_value

        return result

    async def delete_service_config(self, service_name: str, conf_key: str) -> None:
        """删除服务配置项"""
        await db_delete_service_config(service_name, conf_key)

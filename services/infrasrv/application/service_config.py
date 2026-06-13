from cancan_microstack.services.infrasrv.domain.service_config.service_config import ServiceConfig


class ServiceConfigApp:

    def __init__(self):
        self.service_config_domain = ServiceConfig()

    async def get_service_config(self, service_name: str) -> dict:
        return await self.service_config_domain.get_service_config(service_name)

    async def insert_service_config(self, service_name: str, conf_dict: dict) -> None:
        await self.service_config_domain.insert_service_config(service_name, conf_dict)

    async def update_service_config(self, service_name: str, conf_dict: dict) -> None:
        await self.service_config_domain.update_service_config(service_name, conf_dict)

    async def get_all_service_configs(self) -> dict:
        return await self.service_config_domain.get_all_service_configs()

    async def delete_service_config(self, service_name: str, conf_key: str) -> None:
        await self.service_config_domain.delete_service_config(service_name, conf_key)

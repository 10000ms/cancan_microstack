from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.services.infrasrv.application.service_config import ServiceConfigApp

_service_config_app = ServiceConfigApp()


async def get_service_config_handler(service_name: str) -> APIResponse[dict | None]:
    """
    获取服务配置
    供业务服务启动时拉取配置使用
    """
    data = await _service_config_app.get_service_config(service_name)
    return build_success_response(data=data)


async def insert_service_config_handler(service_name: str, conf_data: dict) -> APIResponse[dict]:
    """
    插入服务配置
    供配置管理使用
    """
    await _service_config_app.insert_service_config(service_name, conf_data)
    return build_success_response(data={"message": "Service config inserted successfully"})


async def update_service_config_handler(service_name: str, conf_data: dict) -> APIResponse[dict]:
    """
    更新服务配置
    供配置管理使用
    """
    await _service_config_app.update_service_config(service_name, conf_data)
    return build_success_response(data={"message": "Service config updated successfully"})


async def get_all_service_configs_handler() -> APIResponse[dict]:
    """
    获取所有服务配置
    供配置管理使用
    """
    data = await _service_config_app.get_all_service_configs()
    return build_success_response(data=data)


async def delete_service_config_handler(service_name: str, conf_key: str) -> APIResponse[dict]:
    """
    删除服务配置
    供配置管理使用
    """
    await _service_config_app.delete_service_config(service_name, conf_key)
    return build_success_response(data={"message": "Service config deleted successfully"})

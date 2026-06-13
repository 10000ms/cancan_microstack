"""
服务注册查询API接口
为ops前端提供服务实例查询功能（只读）
"""
from typing import List
import http

from cancan_microstack.public.schemas.common import (
    APIResponse,
)
from cancan_microstack.public.schemas.infra.service_registry import (
    ServiceInstance,
    ServiceInstanceList,
)
from linglong_web import build_success_response
from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.application.service_registry import ServiceRegistryApp

_service_registry_app = ServiceRegistryApp()


async def get_service_instances_handler(
    service_name: str | None = None,
        only_healthy: bool = True,
) -> APIResponse[ServiceInstanceList]:
    """获取服务实例列表"""
    instances: List[ServiceInstance] = await _service_registry_app.get_service_instances(service_name, only_healthy)
    return build_success_response(data=ServiceInstanceList(instances=instances))


async def get_all_instances_handler() -> APIResponse[ServiceInstanceList]:
    """获取所有服务实例"""
    instances: List[ServiceInstance] = await _service_registry_app.get_all_instances()
    return build_success_response(data=ServiceInstanceList(instances=instances))


async def get_instance_handler(
        service_name: str,
        instance_id: str,
) -> APIResponse[ServiceInstance]:
    """获取指定服务实例"""
    instance = await _service_registry_app.get_instance(service_name, instance_id)
    if instance:
        return build_success_response(data=instance)

    raise HTTPException(
        status_code=http.HTTPStatus.NOT_FOUND.value,
        error_code=ErrorCode.HANDLER_NOT_FOUND,
        msg="Instance not found"
    )


async def get_all_service_names_handler() -> APIResponse[List[str]]:
    """获取所有服务名称"""
    service_names = await _service_registry_app.get_all_service_names()
    return build_success_response(data=service_names)


async def get_services_overview_handler() -> APIResponse[List[dict]]:
    """
    获取所有服务的概览信息（包含服务名和状态统计）
    供前端展示服务列表使用
    """
    overview = await _service_registry_app.get_services_overview()
    return build_success_response(data=[o.model_dump() for o in overview])

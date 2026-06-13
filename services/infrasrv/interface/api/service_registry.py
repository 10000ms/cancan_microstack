from typing import List
import http

from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.public.schemas.common import (
    APIResponse,
    MessageResp,
)
from cancan_microstack.public.schemas.infra.enums import (
    HookExecutionResult,
    ServiceType,
)
from cancan_microstack.public.schemas.infra.service_registry import (
    ServiceInstance,
    ServiceInstanceList,
    ServiceRegistryCreate,
)
from linglong_web import build_success_response
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.infrasrv.application.service_registry import ServiceRegistryApp
from cancan_microstack.services.infrasrv.domain.hooks import get_hook_manager
from cancan_microstack.public.schemas.hooks import HookContext
from linglong_web.utils import logger

_service_registry_app = ServiceRegistryApp()
_hook_manager = get_hook_manager()

SERVICE_NAME_TO_TYPE = {
    "infrasrv": ServiceType.INFRASTRUCTURE,
    "opsbffsrv": ServiceType.OPS,
}

# 内置校验类钩子：这些钩子的 FAILURE 视为"校验未通过"，必须真正拒绝注册（返回 400），
# 否则空 host / 坏端口 / 非法服务名等明显非法注册会被放行，使"校验"名不副实。
# 钩子名称见 domain/hooks/builtin_hooks.py。
ENFORCING_VALIDATION_HOOKS = frozenset({
    "service_name_validation",
    "host_validation",
    "port_range_validation",
    "service_quota",
})


async def register_service_handler(
        service: ServiceRegistryCreate,
) -> APIResponse[MessageResp | None]:
    """
    注册服务
    供业务服务启动时注册使用
    """
    logger.info(
        f"Received registration request for service: {service.service_name}, host: '{service.host}', port: {service.port}")

    # 推导服务类型
    service_type = SERVICE_NAME_TO_TYPE.get(service.service_name, ServiceType.BUSINESS)

    # 创建钩子执行上下文
    hook_context = HookContext(
        service_name=service.service_name,
        service_type=service_type,
        instance_id=service.instance_id,
        host=service.host,
        port=service.port,
        metadata=service.service_metadata or {}
    )

    # 执行预注册钩子
    hook_results = await _hook_manager.execute_hooks(hook_context)

    # 检查钩子执行结果
    for hook_result in hook_results:
        if hook_result.result == HookExecutionResult.TERMINATE:  # 钩子主动中断整条链，拒绝注册
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST.value,
                error_code=ErrorCode.REGISTRATION_REJECTED,
                msg=f"Registration rejected by hook {hook_result.hook_name}: {hook_result.message}",
            )
        elif hook_result.result == HookExecutionResult.FAILURE:
            # 内置校验类钩子失败 = 注册信息非法，真正拒绝注册（让"校验"名副其实）。
            if hook_result.hook_name in ENFORCING_VALIDATION_HOOKS:
                raise HTTPException(
                    status_code=http.HTTPStatus.BAD_REQUEST.value,
                    error_code=ErrorCode.REGISTRATION_REJECTED,
                    msg=f"Registration rejected by validation hook {hook_result.hook_name}: {hook_result.message}",
                )
            # 其它（非内置校验）钩子失败维持原行为：仅告警、不拦截。
            logger.warning(f"Hook {hook_result.hook_name} failed: {hook_result.message or hook_result.error}")

    # 如果钩子修改了服务信息，使用修改后的信息
    # 这里可以添加逻辑处理钩子对上下文的修改

    await _service_registry_app.register_service(service)
    return build_success_response(data=MessageResp(message="Service registered successfully"))


async def deregister_service_handler(
        service_name: str,
        instance_id: str,
) -> APIResponse[MessageResp]:
    """
    注销服务
    供业务服务关闭时注销使用
    """
    await _service_registry_app.deregister_service(service_name, instance_id)
    return build_success_response(data=MessageResp(message="Service deregistered successfully"))


async def get_service_instances_handler(
        service_name: str,
        only_healthy: bool = True,
) -> APIResponse[ServiceInstanceList]:
    """
    获取服务实例列表
    供业务服务进行服务发现使用
    """
    instances: List[ServiceInstance] = await _service_registry_app.get_service_instances(service_name, only_healthy)
    return build_success_response(data=ServiceInstanceList(instances=instances))

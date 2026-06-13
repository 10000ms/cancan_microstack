"""
infrasrv 内部实例管理 API

供 controllersrv 调用，用于多实例管理
"""
from typing import Optional
import http

from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.public.const.service_consts import InstanceStatus
from linglong_web.utils import logger
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_instance_op import (
    insert_instance,
    update_instance,
    delete_instance_by_id,
    get_instance_by_id,
    list_instances_by_service,
    count_instances_by_service,
    get_instances_by_status,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_info_op import (
    update_service_replicas,
)
from cancan_microstack.public.schemas.infra.service_instance import ServiceInstanceCreate, ServiceInstanceUpdate


async def internal_create_instance_handler(
        service_name: str,
        instance_id: str,
        container_name: str,
        compose_service_name: str,
        host: str,
        port: int,
        internal_port: int = 8080,
        status: str = InstanceStatus.STARTING,
        expected_status: str = InstanceStatus.RUNNING,
        instance_metadata: Optional[dict] = None,
) -> APIResponse[dict | None]:
    """
    创建实例记录
    
    Args:
        service_name: 服务名称
        instance_id: 实例ID
        container_name: 容器名称
        compose_service_name: Docker Compose 服务名
        host: 宿主机地址
        port: 服务端口
        internal_port: 容器内部端口
        status: 实例状态
        expected_status: 期望状态
        instance_metadata: 实例元数据
    """
    instance_data = ServiceInstanceCreate(
        service_name=service_name,
        instance_id=instance_id,
        container_name=container_name,
        compose_service_name=compose_service_name,
        host=host,
        port=port,
        internal_port=internal_port,
        status=status,
        expected_status=expected_status,
        instance_metadata=instance_metadata or {}
    )

    await insert_instance(instance_data)

    logger.info(f"Instance created: {instance_id}")
    return build_success_response(data={"instance_id": instance_id})


async def internal_update_instance_handler(
        instance_id: str,
        status: Optional[str] = None,
        health_status: Optional[str] = None,
        started_at: Optional[str] = None,
        stopped_at: Optional[str] = None,
        last_heartbeat: Optional[str] = None,
        consecutive_failures: Optional[int] = None,
        instance_metadata: Optional[dict] = None,
) -> APIResponse[dict | None]:
    """
    更新实例信息
    
    Args:
        instance_id: 实例ID
        status: 实例状态
        health_status: 健康状态
        started_at: 启动时间
        stopped_at: 停止时间
        last_heartbeat: 最后心跳时间
        consecutive_failures: 连续失败次数
        instance_metadata: 实例元数据
    """
    # 注意：last_heartbeat 映射到 last_health_check
    update_data = ServiceInstanceUpdate(
        status=status,
        health_status=health_status,
        started_at=started_at,
        stopped_at=stopped_at,
        last_health_check=last_heartbeat,
        consecutive_failures=consecutive_failures,
        instance_metadata=instance_metadata
    )

    await update_instance(instance_id, update_data)

    logger.debug(f"Instance updated: {instance_id}")
    return build_success_response(data={"instance_id": instance_id})


async def internal_delete_instance_handler(instance_id: str) -> APIResponse[dict | None]:
    """
    删除实例记录
    
    Args:
        instance_id: 实例ID
    """
    await delete_instance_by_id(instance_id)

    logger.info(f"Instance deleted: {instance_id}")
    return build_success_response(data={"instance_id": instance_id})


async def internal_get_instance_handler(instance_id: str) -> APIResponse[dict | None]:
    """
    获取实例信息
    
    Args:
        instance_id: 实例ID
    """
    instance = await get_instance_by_id(instance_id)

    if not instance:
        raise HTTPException(
            status_code=http.HTTPStatus.NOT_FOUND.value,
            error_code=ErrorCode.HANDLER_NOT_FOUND,
            msg="Instance not found",
        )

    return build_success_response(data=instance.model_dump())


async def internal_list_instances_handler(
        service_name: Optional[str] = None,
        status: Optional[str] = None,
) -> APIResponse[dict]:
    """
    列出实例
    
    Args:
        service_name: 服务名称（可选）
        status: 状态过滤（可选）
    """
    if status:
        instances = await get_instances_by_status(status)
        if service_name:
            instances = [i for i in instances if i.service_name == service_name]
    elif service_name:
        instances = await list_instances_by_service(service_name)
    else:
        # 获取所有实例
        instances = await get_instances_by_status(InstanceStatus.RUNNING)
        instances.extend(await get_instances_by_status(InstanceStatus.STOPPED))
        instances.extend(await get_instances_by_status(InstanceStatus.STARTING))
        instances.extend(await get_instances_by_status(InstanceStatus.STOPPING))

    return build_success_response(
        data={
            "instances": [i.model_dump() for i in instances],
            "count": len(instances),
        }
    )


async def internal_count_instances_handler(
        service_name: str,
        status: Optional[str] = None,
) -> APIResponse[dict]:
    """
    统计实例数量
    
    Args:
        service_name: 服务名称
        status: 状态过滤（可选）
    """
    count = await count_instances_by_service(service_name, status)

    return build_success_response(data={"count": count})


async def internal_get_next_port_handler(
        service_name: str,
        start_port: int,
        end_port: int,
) -> APIResponse[dict | None]:
    """
    获取服务的下一个可用端口
    
    Args:
        service_name: 服务名称
        start_port: 起始端口
        end_port: 结束端口
    """
    # 获取服务的所有实例
    instances = await list_instances_by_service(service_name)

    # 获取已使用的端口
    used_ports = {inst.port for inst in instances if inst.port}

    # 查找第一个可用端口
    for port in range(start_port, end_port + 1):
        if port not in used_ports:
            logger.debug(f"Allocated port {port} for service {service_name}")
            return build_success_response(data={"port": port})

    # 没有可用端口
    logger.warning(f"No available ports for service {service_name} in range {start_port}-{end_port}")
    raise HTTPException(
        status_code=http.HTTPStatus.SERVICE_UNAVAILABLE.value,
        error_code=ErrorCode.SYSTEM_ERROR,
        msg="No available ports",
    )


async def internal_update_service_replicas_handler(
        service_name: str,
        desired_replicas: int,
        actual_replicas: int,
        last_scale_at: Optional[str] = None,
) -> APIResponse[dict]:
    """
    记录服务的副本数信息（仅记录期望状态，不实际扩缩容）

    ⚠️ 重要：本接口仅把 desired_replicas / actual_replicas 写入 service_info 表，
    用于记录"期望副本数（desired state）"和上游上报的"实际副本数"。
    它**不会真正增减运行中的容器**——infrasrv 没有扩缩容执行能力，
    controllersrv 也未实现 scale 动作。要真正改变运行实例数，需由外部编排
    （如手动 docker-compose scale）完成后，再由上游调用本接口回填 actual_replicas。

    Args:
        service_name: 服务名称
        desired_replicas: 期望副本数（仅记录，不触发扩缩容）
        actual_replicas: 实际副本数（由上游上报回填，本接口不会去核对真实容器数）
        last_scale_at: 最后扩缩容时间 (API 参数保留，但 op 层在 desired_replicas 变更时自动写入)
    """
    service_info = await update_service_replicas(
        service_name=service_name,
        desired_replicas=desired_replicas,
        actual_replicas=actual_replicas,
    )

    if not service_info:
        raise HTTPException(
            status_code=http.HTTPStatus.NOT_FOUND.value,
            error_code=ErrorCode.HANDLER_NOT_FOUND,
            msg=f"Service info not found for {service_name}"
        )

    logger.info(f"Service replicas updated: {service_name} (desired={desired_replicas}, actual={actual_replicas})")
    return build_success_response(data=service_info.model_dump())

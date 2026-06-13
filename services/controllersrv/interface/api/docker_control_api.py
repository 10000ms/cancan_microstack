"""
Docker 控制 API 接口层

职责：
1. 参数验证
2. 服务名称验证
3. 流水号检查
4. 任务入队（操作型 API）
5. 直接查询（查询型 API）
6. 返回统一响应格式
"""
from typing import (
    Optional,
)

from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import (
    build_success_response,
)
from linglong_web import limiter_local
from linglong_web import LinglongConfig
from cancan_microstack.public.const.operation_consts import OperationType, OperationStatus
from cancan_microstack.public.schemas.controllersrv.requests import (
    ServiceOperationRequest,
    TaskQueryRequest,
    ServiceStatusRequest,
)
from cancan_microstack.public.schemas.controllersrv.responses import (
    EnqueueSuccessResponse,
    TaskStatusResponse,
    TaskListResponse,
    QueueStatsResponse,
    ServiceStatusResponse,
    ServiceListResponse,
    ContainerHealthResponse,
    ComposeStatusResponse,
)
from cancan_microstack.public.schemas.controllersrv.docker_responses import (
    ContainerListResponse,
    ContainerDetailResponse,
    ContainerLogsResponse,
    ImageListResponse,
    NetworkListResponse,
    VolumeListResponse,
    EngineHealthResponse,
)
from cancan_microstack.public.const.controllersrv_consts import (
    ControllersrvErrorCode,
    ValidationResultKey,
)
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.controllersrv.domain.service_validator import get_service_validator
from cancan_microstack.services.controllersrv.application.docker_compose_app import DockerComposeApp
from cancan_microstack.services.controllersrv.domain.docker_compose.docker_compose_domain import DockerComposeDomain
from dragonfly_container.core import ExecutorFactory
from linglong_web.utils import logger

# 应用层实例（懒加载）/ Lazily cached application instance
_docker_compose_app: Optional[DockerComposeApp] = None


def _get_app() -> DockerComposeApp:
    """获取应用层实例（直接使用 Dragonfly Container UnifiedExecutor）"""
    global _docker_compose_app
    if _docker_compose_app is None:
        # 创建 UnifiedExecutor（自动检测容器引擎）
        executor = ExecutorFactory.create_unified_executor(
            compose_file=LinglongConfig.DOCKER_COMPOSE_FILE,
            project_name=LinglongConfig.DOCKER_COMPOSE_PROJECT_NAME
        )

        # 创建领域层
        domain = DockerComposeDomain(executor)

        # 创建应用层
        _docker_compose_app = DockerComposeApp(domain)

        logger.info("Application initialized with Dragonfly Container")

    return _docker_compose_app


def _validate_services_or_raise(service_names: list) -> None:
    """
    验证服务名称是否合法，不合法则抛出异常
    
    Args:
        service_names: 服务名称列表
    
    Raises:
        HTTPException: 如果验证失败
    """
    validator = get_service_validator()
    if not validator:
        logger.warning("Service validator not initialized, skipping validation")
        return

    # Get dict result from validator
    validation_dict = validator.validate_service_names(service_names)

    if not validation_dict[ValidationResultKey.VALID]:
        error_msg = []
        invalid_services = validation_dict[ValidationResultKey.INVALID_SERVICES]
        non_operable_services = validation_dict[ValidationResultKey.NON_OPERABLE_SERVICES]

        if invalid_services:
            error_msg.append(f"Invalid services: {invalid_services}")
        if non_operable_services:
            error_msg.append(f"Non-operable services: {non_operable_services}")

        raise HTTPException(
            error_code=ControllersrvErrorCode.INVALID_SERVICE_NAME,
            msg="; ".join(error_msg),
        )


@limiter_local("10/minute")
async def service_start_handler(
        request: ServiceOperationRequest,
) -> APIResponse[EnqueueSuccessResponse]:
    """
    启动服务
    
    流程：
    1. 参数验证（Pydantic 自动完成）
    2. 服务名称验证
    3. 创建任务并入队
    4. 返回"执行中"状态
    
    Args:
        request: 服务操作请求对象
    
    Returns:
        统一响应格式
    """
    logger.info(f"Received service start request: {request}")

    # 1. 验证服务名称
    _validate_services_or_raise(request.service_names)

    # 2. 创建任务并入队
    app = _get_app()
    result = await app.create_operation_task(
        serial_number=request.serial_number,
        operation=OperationType.START,
        service_names=request.service_names,
        params=request.params
    )

    # 3. 返回结果
    return build_success_response(data=result)


@limiter_local("10/minute")
async def service_stop_handler(
        request: ServiceOperationRequest,
) -> APIResponse[EnqueueSuccessResponse]:
    """
    停止服务
    
    Args:
        request: 服务操作请求对象
    
    Returns:
        统一响应格式
    """
    logger.info(f"Received service stop request: {request}")

    # 验证服务名称
    _validate_services_or_raise(request.service_names)

    # 创建任务并入队
    app = _get_app()
    result = await app.create_operation_task(
        serial_number=request.serial_number,
        operation=OperationType.STOP,
        service_names=request.service_names,
        params=request.params
    )

    # 返回结果
    return build_success_response(data=result)


@limiter_local("10/minute")
async def service_restart_handler(
        request: ServiceOperationRequest,
) -> APIResponse[EnqueueSuccessResponse]:
    """
    重启服务
    
    Args:
        request: 服务操作请求对象
    
    Returns:
        统一响应格式
    """
    logger.info(f"Received service restart request: {request}")

    # 验证服务名称
    _validate_services_or_raise(request.service_names)

    # 创建任务并入队
    app = _get_app()
    result = await app.create_operation_task(
        serial_number=request.serial_number,
        operation=OperationType.RESTART,
        service_names=request.service_names,
        params=request.params
    )

    # 返回结果
    return build_success_response(data=result)



# ==================== 查询型 API ====================

@limiter_local("10/minute")
async def task_status_handler(
        serial_number: str,
) -> APIResponse[TaskStatusResponse]:
    """
    查询任务状态
    
    Args:
        serial_number: 流水号
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.get_task_status(serial_number)

    return build_success_response(
        data=result,
    )


@limiter_local("10/minute")
async def task_list_handler(
        request: TaskQueryRequest,
) -> APIResponse[TaskListResponse]:
    """
    列出任务
    
    Args:
        request: 任务查询请求
    
    Returns:
        统一响应格式
    """
    app = _get_app()

    # 解析状态过滤
    status_filter = None
    if request.status:
        try:
            status_filter = OperationStatus(request.status)
        except ValueError:
            raise HTTPException(
                error_code=ControllersrvErrorCode.INVALID_PARAMETER,
                msg=f"Invalid status value: {request.status}",
            )

    result = await app.list_tasks(status=status_filter, limit=request.limit)
    return build_success_response(data=result)


@limiter_local("10/minute")
async def queue_stats_handler() -> APIResponse[QueueStatsResponse]:
    """
    获取队列统计信息
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.get_queue_stats()
    return build_success_response(data=result)


@limiter_local("30/minute")
async def service_status_handler(
        request: ServiceStatusRequest,
) -> APIResponse[ServiceStatusResponse]:
    """
    查询服务状态
    
    Args:
        request: 服务状态请求对象
    
    Returns:
        统一响应格式
    """
    # 验证服务名称
    _validate_services_or_raise(request.service_names)

    # 获取服务状态
    app = _get_app()
    result = await app.get_service_status(request.service_names)

    return build_success_response(data=result)


@limiter_local("10/minute")
async def service_list_handler() -> APIResponse[ServiceListResponse]:
    """
    列出所有服务（使用 API Executor）
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.list_services()

    return build_success_response(data=result)


@limiter_local("10/minute")
async def container_health_handler(
        service_name: str,
) -> APIResponse[ContainerHealthResponse]:
    """
    检查容器健康状态（使用 API Executor）
    
    Args:
        service_name: 服务名称
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.get_container_health(service_name)

    return build_success_response(data=result)


@limiter_local("30/minute")
async def compose_status_handler() -> APIResponse[ComposeStatusResponse]:
    """
    获取 Compose 状态
    
    Returns:
        统一响应格式
    """
    # 获取 Compose 状态（不需要参数）
    app = _get_app()
    result = await app.get_compose_status()

    return build_success_response(data=result)


# ==================== 基于 UnifiedExecutor API 的容器管理接口 ====================

@limiter_local("10/minute")
async def containers_list_handler(
        include_stopped: bool = False,
) -> APIResponse[ContainerListResponse]:
    """
    列出容器（使用 API Executor）
    
    Args:
        include_stopped: 是否包括已停止的容器
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.list_containers(include_stopped=include_stopped)

    return build_success_response(data=result)


@limiter_local("10/minute")
async def container_inspect_handler(
        container_id: str,
) -> APIResponse[ContainerDetailResponse]:
    """
    检查容器详细信息（使用 API Executor）
    
    Args:
        container_id: 容器 ID 或名称
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.inspect_container(container_id)

    return build_success_response(data=result)


@limiter_local("10/minute")
async def container_logs_handler(
        container_id: str,
        tail: int = 100,
        since: Optional[str] = None,
) -> APIResponse[ContainerLogsResponse]:
    """
    获取容器日志（使用 API Executor）
    
    Args:
        container_id: 容器 ID 或名称
        tail: 返回最后 N 行
        since: 时间戳，返回此时间之后的日志
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.get_container_logs(container_id, tail=tail, since=since)

    return build_success_response(data=result)


@limiter_local("10/minute")
async def images_list_handler() -> APIResponse[ImageListResponse]:
    """
    列出镜像（使用 API Executor）
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.list_images()

    return build_success_response(data=result)


@limiter_local("10/minute")
async def networks_list_handler() -> APIResponse[NetworkListResponse]:
    """
    列出网络（使用 API Executor）
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.list_networks()

    return build_success_response(data=result)


@limiter_local("10/minute")
async def volumes_list_handler() -> APIResponse[VolumeListResponse]:
    """
    列出卷（使用 API Executor）
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.list_volumes()

    return build_success_response(data=result)


@limiter_local("10/minute")
async def engine_health_handler() -> APIResponse[EngineHealthResponse]:
    """
    检查引擎健康状态（使用 API Executor）
    
    Returns:
        统一响应格式
    """
    app = _get_app()
    result = await app.get_engine_health()

    return build_success_response(data=result)

"""
Docker Compose 管理应用层

职责：
1. 接收 API 请求
2. 创建任务并入队（操作型 API）
3. 直接查询并返回（查询型 API）
"""
from typing import (
    Dict,
    Any,
    Optional,
    List,
    Union,
)

from linglong_web.utils import logger
from cancan_microstack.public.error import (
    HTTPException,
    ParamError,
)
from cancan_microstack.public.const.controllersrv_consts import ControllersrvErrorCode
from cancan_microstack.public.const.operation_consts import OperationStatus
from cancan_microstack.public.schemas.controllersrv.responses import (
    EnqueueSuccessResponse,
    TaskNotFoundResponse,
    TaskStatusResponse,
    TaskListResponse,
    QueueStatsResponse,
    ServiceStatusResponse,
    ServiceListResponse,
    ContainerHealthResponse,
    ComposeStatusResponse,
)
from cancan_microstack.public.schemas.controllersrv.docker_responses import (
    ContainerInfo,
    ContainerListResponse,
    ContainerDetailResponse,
    ContainerLogsResponse,
    ImageInfo,
    ImageListResponse,
    NetworkInfo,
    NetworkListResponse,
    VolumeInfo,
    VolumeListResponse,
    EngineInfo,
    EngineHealthResponse,
)
from cancan_microstack.public.const.operation_consts import (
    OperationType,
)
from cancan_microstack.public.schemas.controllersrv.task_models import Task
from cancan_microstack.services.controllersrv.domain.task.task_queue import get_task_queue
from cancan_microstack.services.controllersrv.domain.docker_compose.docker_compose_domain import DockerComposeDomain


class DockerComposeApp:
    """
    应用层：负责任务创建和查询功能
    """

    def __init__(self, domain: DockerComposeDomain):
        """
        初始化应用层
        
        Args:
            domain: 领域层实例
        """
        self.domain = domain
        self.task_queue = get_task_queue()
        logger.info("DockerComposeApp initialized")

    async def create_operation_task(
            self,
            serial_number: str,
            operation: OperationType,
            service_names: List[str],
            params: Optional[Dict[str, Any]] = None,
    ) -> EnqueueSuccessResponse:
        """
        创建操作任务并入队
        
        Args:
            serial_number: 流水号
            operation: 操作类型
            service_names: 服务名称列表
            params: 额外参数
        
        Returns:
            入队结果对象
        """
        try:
            # 创建任务
            task = Task(
                serial_number=serial_number,
                operation=operation,
                service_names=service_names,
                params=params or {},
            )

            # 入队
            enqueued = await self.task_queue.enqueue(task)

            # 队列已满时 enqueue 返回 False，必须显式失败，不能再无条件返回成功
            # enqueue returns False when the queue is full; fail explicitly instead of reporting success
            if not enqueued:
                logger.warning(f"Task queue is full, rejecting task: serial={serial_number}")
                raise HTTPException(
                    error_code=ControllersrvErrorCode.TASK_QUEUE_FULL,
                    msg="Task queue is full"
                )

            logger.info(
                f"Task enqueued: serial={serial_number}, "
                f"operation={operation}, "
                f"services={service_names}"
            )

            return EnqueueSuccessResponse(
                serial_number=serial_number,
                operation=operation,
                service_names=service_names,
            )

        except ValueError as e:
            # 流水号重复
            logger.warning(f"Duplicate serial number: {serial_number}")
            raise HTTPException(
                error_code=ControllersrvErrorCode.DUPLICATE_SERIAL_NUMBER,
                msg=str(e)
            )

        except HTTPException:
            # 已是明确的 HTTP 错误（如队列已满），直接向上抛出，避免被下面的通用处理重新包装
            # Already a precise HTTP error (e.g. queue full); re-raise so the generic handler below does not re-wrap it
            raise

        except Exception as e:
            # 其他错误
            logger.error(f"Failed to enqueue task: {e}", exc_info=True)
            raise HTTPException(
                error_code=ControllersrvErrorCode.OPERATION_FAILED,
                msg=f"Failed to enqueue task: {str(e)}"
            )

    async def get_task_status(self, serial_number: str) -> Union[TaskStatusResponse, TaskNotFoundResponse]:
        """
        查询任务状态
        
        Args:
            serial_number: 流水号
        
        Returns:
            任务状态信息
        """
        task = await self.task_queue.get_task(serial_number)

        if not task:
            raise ParamError("serial_number")

        return TaskStatusResponse(task=task.to_dict())

    async def list_tasks(
            self,
            status: Optional[OperationStatus] = None,
            limit: int = 100
    ) -> TaskListResponse:
        """
        列出任务
        
        Args:
            status: 过滤状态
            limit: 最大返回数量
        
        Returns:
            任务列表响应对象
        """
        tasks = await self.task_queue.list_tasks(status=status, limit=limit)
        return TaskListResponse(tasks=tasks, count=len(tasks))

    async def get_queue_stats(self) -> QueueStatsResponse:
        """
        获取队列统计信息
        
        Returns:
            队列统计信息响应对象
        """
        # 获取队列统计（返回 TaskQueueStats Pydantic 模型）
        stats = await self.task_queue.get_queue_stats()

        # 直接返回嵌套的 stats 对象
        return QueueStatsResponse(
            success=True,
            stats=stats
        )

    async def get_service_status(self, service_names: Optional[List[str]] = None) -> ServiceStatusResponse:
        """
        获取服务状态（查询型 API，使用 API Executor）
        
        Args:
            service_names: 服务名称列表，None 表示获取所有服务状态
        
        Returns:
            服务状态响应对象
        """
        logger.info(f"Getting service status: {service_names or 'all'}")
        # 调用领域层获取服务状态
        result = await self.domain.get_service_status(service_names)

        # domain层返回的是ServiceListResult对象
        return ServiceStatusResponse(
            success=result.success,
            services=result.services,
            error=getattr(result, 'error', None),
        )

    async def list_services(self) -> ServiceListResponse:
        """
        列出所有服务（查询型 API，使用 API Executor）
        
        Returns:
            服务列表响应对象
        """
        logger.info("Listing all services")
        # 调用领域层列出服务
        result = await self.domain.list_services()

        # domain层返回的是ServiceListResult对象
        return ServiceListResponse(
            success=result.success,
            services=result.services,
            error=getattr(result, 'error', None)
        )

    async def get_container_health(self, service_name: str) -> ContainerHealthResponse:
        """
        获取容器健康状态（查询型 API，使用 API Executor）
        
        Args:
            service_name: 服务名称
        
        Returns:
            容器健康状态响应对象
        """
        logger.info(f"Getting container health for service: {service_name}")
        # 调用领域层获取容器健康状态
        result = await self.domain.get_container_health(service_name)

        # domain层返回的是ContainerHealthResult对象
        # 将 ContainerHealthDetail 列表转换为字典列表
        containers_dict = [c.model_dump() for c in result.containers] if result.containers else []
        return ContainerHealthResponse(
            success=result.success,
            service_name=service_name,
            containers=containers_dict,
            error=getattr(result, 'error', None)
        )

    async def get_compose_status(self) -> ComposeStatusResponse:
        """
        获取 Docker Compose 整体状态（查询型 API，使用 API Executor）
        
        Returns:
            Docker Compose 状态响应对象
        """
        logger.info("Getting Docker Compose status")
        # 调用领域层获取 Compose 状态
        result = await self.domain.get_compose_status()

        # domain层返回的是ComposeStatusResult对象
        return ComposeStatusResponse(
            success=result.success,
            is_running=result.is_running,
            service_count=result.service_count,
            services=result.services,
            error=getattr(result, 'error', None)
        )

    # ==================== 新增：基于 UnifiedExecutor API 的容器管理方法 ====================

    async def list_containers(self, include_stopped: bool = False) -> ContainerListResponse:
        """
        列出容器（使用 API）
        
        Args:
            include_stopped: 是否包括已停止的容器
        
        Returns:
            容器列表响应对象
        """
        containers = await self.domain.executor.list_containers(all=include_stopped)
        return ContainerListResponse(
            success=True,
            containers=[
                ContainerInfo(
                    id=c.id,
                    name=c.name,
                    status=c.status,
                    image=c.image,
                    created=c.created.isoformat() if c.created else None,
                    ports=c.ports,
                    labels=c.labels,
                )
                for c in containers
            ]
        )

    async def inspect_container(self, container_id: str) -> ContainerDetailResponse:
        """
        检查容器详细信息（使用 API）
        
        Args:
            container_id: 容器 ID 或名称
        
        Returns:
            容器详细信息响应对象
        """
        detail = await self.domain.executor.inspect_container(container_id)
        return ContainerDetailResponse(success=True, container=detail)

    async def get_container_logs(
            self,
            container_id: str,
            tail: int = 100,
            since: Optional[str] = None
    ) -> ContainerLogsResponse:
        """
        获取容器日志（使用 API）
        
        Args:
            container_id: 容器 ID 或名称
            tail: 返回最后 N 行
            since: 时间戳，返回此时间之后的日志
        
        Returns:
            容器日志响应对象
        """
        logs = await self.domain.executor.get_container_logs(
            container_id,
            tail=tail,
            since=since,
        )
        return ContainerLogsResponse(success=True, logs=logs)

    async def list_images(self) -> ImageListResponse:
        """
        列出镜像（使用 API）
        
        Returns:
            镜像列表响应对象
        """
        images = await self.domain.executor.list_images()
        return ImageListResponse(
            success=True,
            images=[
                ImageInfo(
                    id=img.id,
                    tags=img.tags,
                    size=img.size,
                    created=img.created.isoformat() if img.created else None,
                )
                for img in images
            ]
        )

    async def list_networks(self) -> NetworkListResponse:
        """
        列出网络（使用 API）
        
        Returns:
            网络列表响应对象
        """
        networks = await self.domain.executor.list_networks()
        return NetworkListResponse(
            success=True,
            networks=[
                NetworkInfo(
                    id=net.id,
                    name=net.name,
                    driver=net.driver,
                    scope=net.scope,
                    containers=net.containers,
                )
                for net in networks
            ]
        )

    async def list_volumes(self) -> VolumeListResponse:
        """
        列出卷（使用 API）
        
        Returns:
            卷列表响应对象
        """
        volumes = await self.domain.executor.list_volumes()
        return VolumeListResponse(
            success=True,
            volumes=[
                VolumeInfo(
                    name=vol.name,
                    driver=vol.driver,
                    mountpoint=vol.mountpoint,
                )
                for vol in volumes
            ]
        )

    async def get_engine_health(self) -> EngineHealthResponse:
        """
        检查引擎健康状态（使用 API）
        
        Returns:
            引擎健康状态响应对象
        """
        is_healthy = await self.domain.executor.check_engine_health()
        engine_info = await self.domain.executor.get_engine_info()
        return EngineHealthResponse(
            success=True,
            healthy=is_healthy,
            engine_info=EngineInfo(
                version=engine_info.version,
                api_version=engine_info.api_version,
                os_type=engine_info.os_type,
                architecture=engine_info.architecture,
            )
        )

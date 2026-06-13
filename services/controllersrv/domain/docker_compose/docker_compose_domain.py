"""
Docker Compose 管理领域层（重构版 - 使用 UnifiedExecutor）

职责：
1. 使用 UnifiedExecutor 进行容器操作
2. API 操作：用于查询容器、镜像、网络等（快速、结构化）
3. Compose 操作：用于服务编排（启动、停止、扩缩容等）
4. 不包含业务验证逻辑
"""
import asyncio
from typing import (
    List,
    Optional,
)

from linglong_web.utils import logger
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.controllersrv_consts import ControllersrvErrorCode
from cancan_microstack.public.schemas.controllersrv.docker_models import (
    ContainerHealthDetail,
    ContainerState,
    HealthCheck,
)
from cancan_microstack.public.const.docker_consts import (
    DockerLabel,
    DockerInspectKey,
)
from dragonfly_container.core import UnifiedExecutor
from cancan_microstack.public.schemas.controllersrv.compose_models import (
    CommandResult,
    ServiceListResult,
    ContainerHealthResult,
    ComposeStatusResult,
)


class DockerComposeDomain:
    """
    Docker Compose 领域层（直接使用 Dragonfly Container UnifiedExecutor）
    
    直接使用 UnifiedExecutor 进行容器管理和服务编排
    - API 操作：用于查询和单容器控制（基于 SDK）
    - Compose 操作：用于多服务编排（基于 CLI）
    """

    def __init__(self, executor: UnifiedExecutor):
        """
        初始化领域层
        
        Args:
            executor: Dragonfly Container UnifiedExecutor 实例
        """
        self.executor = executor
        logger.info(
            f"DockerComposeDomain initialized with UnifiedExecutor: "
            f"engine={executor.api.engine_type}"
        )

    async def execute_command(
            self,
            cmd: List[str],
            timeout: int,
            operation_name: str
    ) -> CommandResult:
        """
        执行命令
        
        Args:
            cmd: 命令列表
            timeout: 超时时间（秒）
            operation_name: 操作名称（用于日志）
        
        Returns:
            执行结果对象
        """
        logger.info(f"[{operation_name}] Executing: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise Exception(f"Command timeout after {timeout}s")

            success = process.returncode == 0
            output = stdout.decode('utf-8', errors='ignore').strip()
            error = stderr.decode('utf-8', errors='ignore').strip()

            if success:
                logger.info(f"[{operation_name}] Command succeeded")
            else:
                logger.error(
                    f"[{operation_name}] Command failed with code {process.returncode}: {error}"
                )

            return CommandResult(
                success=success,
                output=output,
                error=error,
                returncode=process.returncode,
            )

        except Exception as e:
            logger.error(f"[{operation_name}] Command execution error: {e}", exc_info=True)
            return CommandResult(
                success=False,
                output="",
                error=str(e),
                returncode=-1,
            )

    async def check_compose_running(self) -> bool:
        """
        检查 Docker Compose 是否正在运行（使用 API）
        
        Returns:
            True 表示有容器在运行
        """
        try:
            # 使用 API 查询当前项目的容器
            containers = await self.executor.list_containers()

            if containers:
                logger.info(f"Docker Compose is running: {len(containers)} containers found")
                return True

            logger.info("Docker Compose is not running: no containers found")
            return False

        except Exception as e:
            logger.error(f"Failed to check compose status: {e}", exc_info=True)
            return False

    async def get_service_status(self, service_names: Optional[List[str]] = None) -> ServiceListResult:
        """
        获取服务状态（使用 API）
        
        Args:
            service_names: 服务名称列表，None 表示获取所有服务状态
        
        Returns:
            服务状态结果对象
        """
        # 使用 API 查询容器
        containers = await self.executor.list_containers(all=True)

        # 如果指定了服务名称，则过滤
        if service_names:
            # 过滤出指定服务的容器
            # 容器名称格式通常是 project_service_1
            filtered_containers = []
            for container in containers:
                # 检查标签中的 com.docker.compose.service
                service = container.labels.get(DockerLabel.SERVICE, "")
                if service in service_names:
                    filtered_containers.append(container)
            containers = filtered_containers

        # 构建服务列表（格式化输出，类似 docker-compose ps）
        services = []
        for container in containers:
            service_name = container.labels.get(DockerLabel.SERVICE, "unknown")
            services.append(
                f"{container.name}\t{service_name}\t{container.status}\t{container.image}"
            )

        return ServiceListResult(
            success=True,
            services=services
        )

    async def list_services(self) -> ServiceListResult:
        """
        列出所有服务（使用 API 从容器标签中提取）
        
        Returns:
            服务列表结果对象
        """
        # 使用 API 查询所有容器（包括已停止的）
        containers = await self.executor.list_containers(all=True)

        # 从容器标签中提取唯一的服务名称
        services = set()
        for container in containers:
            service_name = container.labels.get(DockerLabel.SERVICE, "")
            if service_name:
                services.add(service_name)

        return ServiceListResult(
            success=True,
            services=sorted(list(services))
        )

    async def get_container_health(self, service_name: str) -> ContainerHealthResult:
        """
        获取容器健康状态（使用 API）
        
        Args:
            service_name: 服务名称
        
        Returns:
            容器健康状态结果对象
        """
        # 使用 API 查询所有容器
        all_containers = await self.executor.list_containers(all=True)

        # 过滤出指定服务的容器
        service_containers = []
        for container in all_containers:
            if container.labels.get(DockerLabel.SERVICE) == service_name:
                service_containers.append(container)

        if not service_containers:
            raise HTTPException(
                error_code=ControllersrvErrorCode.SERVICE_NOT_FOUND,
                msg=f"No containers found for service: {service_name}"
            )

        # 获取每个容器的详细信息
        containers = []
        for container in service_containers:
            try:
                # 使用 API 获取详细信息
                detail = await self.executor.inspect_container(container.id)
                state_data = detail.get(DockerInspectKey.STATE, {})
                health_data = state_data.get(DockerInspectKey.HEALTH, {})

                containers.append(
                    ContainerHealthDetail(
                        id=container.id,
                        name=container.name,
                        state=ContainerState.model_validate(state_data) if state_data else None,
                        health=HealthCheck.model_validate(health_data) if health_data else None,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to inspect container {container.id}: {e}")
                # 使用基础信息作为备用
                containers.append(
                    ContainerHealthDetail(
                        id=container.id,
                        name=container.name,
                        state=None,
                        health=None,
                    )
                )

        return ContainerHealthResult(success=True, containers=containers)

    async def get_compose_status(self) -> ComposeStatusResult:
        """
        获取 Docker Compose 整体状态（使用 API）
        
        Returns:
            Docker Compose 状态结果对象
        """
        is_running = await self.check_compose_running()
        services_info = await self.list_services()
        status_info = await self.get_service_status()

        return ComposeStatusResult(
            is_running=is_running,
            project_name=self.executor.project_name,
            compose_file=self.executor.compose.compose_file,
            engine_type=str(self.executor.api.engine_type),
            available_services=services_info.services,
            running_services=status_info.services,
        )

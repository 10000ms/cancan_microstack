"""
controllersrv API 客户端（用于 infrasrv）/ controllersrv API Client (for infrasrv)

infrasrv 用于调用 controllersrv 的 API 客户端 / API client for infrasrv to call controllersrv
继承自公共的 ControllerSrvApiClient / Inherits from common ControllerSrvApiClient
"""
import os
from typing import (
    List,
    Optional,
)

from linglong_web.utils import logger
from linglong_web import LinglongConfig

from cancan_microstack.public.api.controllersrv_client import (
    ControllerSrvApiClient,
    ServiceOperationResponse,
)
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.controllersrv.responses import (
    EnqueueErrorResponse,
    EnqueueSuccessResponse,
    TaskStatusResponse,
)
from cancan_microstack.public.schemas.controllersrv.validation import ValidationResult
from cancan_microstack.public.schemas.infra.service_management import ControllerSrvResult


class ControllerSrvApi(ControllerSrvApiClient):
    """
    用于与 controllersrv 通信的 API 客户端（infrasrv 专用）
    API client for communicating with controllersrv (for infrasrv)
    
    继承自公共的 ControllerSrvApiClient，添加特定于 infrasrv 的配置
    Inherits from common ControllerSrvApiClient with infrasrv-specific configuration
    """

    def __init__(self):
        """
        初始化 API 客户端，使用 infrasrv 的配置
        Initialize API client with infrasrv configuration
        """
        # 从配置获取 controllersrv 的地址 / Get controllersrv address from config
        # 优先使用环境变量，确保在容器环境中能获取到正确的值
        # 注意：该类可能会在 LinglongConfig 初始化前被 import。
        # Note: This class may be imported before LinglongConfig is initialized.
        config_host = getattr(LinglongConfig, "CONTROLLERSRV_HOST", None)
        controllersrv_host = os.getenv(
            "CONTROLLERSRV_HOST",
            config_host or "http://host.containers.internal:22100",
        )

        base_url = f"{controllersrv_host}/v1/controllersrv"

        # 调用父类初始化 / Call parent class initialization
        super().__init__(base_url=base_url)
        logger.info(f"ControllerSrvApi initialized (infrasrv) with base_url: {base_url}")

    async def start_services(self, service_names: List[str], serial_number: str) -> ControllerSrvResult:
        """
        调用 controllersrv 启动服务 / Call controllersrv to start services
        
        Args:
            service_names: 服务名称列表 / List of service names
            serial_number: 操作序列号（operation_id）/ Operation serial number (operation_id)
        
        Returns:
            操作结果 / Operation result
        """
        logger.info(f"[infrasrv → controllersrv] Starting services: {service_names}, serial_number: {serial_number}")
        response = await super().start_services(service_names, serial_number)
        return self._to_controller_result(response, operation="start")

    async def stop_services(self, service_names: List[str], serial_number: str) -> ControllerSrvResult:
        """
        调用 controllersrv 停止服务 / Call controllersrv to stop services
        
        Args:
            service_names: 服务名称列表 / List of service names
            serial_number: 操作序列号（operation_id）/ Operation serial number (operation_id)
        
        Returns:
            操作结果 / Operation result
        """
        logger.info(f"[infrasrv → controllersrv] Stopping services: {service_names}, serial_number: {serial_number}")
        response = await super().stop_services(service_names, serial_number)
        return self._to_controller_result(response, operation="stop")

    async def restart_services(self, service_names: List[str], serial_number: str) -> ControllerSrvResult:
        """
        调用 controllersrv 重启服务 / Call controllersrv to restart services
        
        Args:
            service_names: 服务名称列表 / List of service names
            serial_number: 操作序列号（operation_id）/ Operation serial number (operation_id)
        
        Returns:
            操作结果 / Operation result
        """
        logger.info(f"[infrasrv → controllersrv] Restarting services: {service_names}, serial_number: {serial_number}")
        response = await super().restart_services(service_names, serial_number)
        return self._to_controller_result(response, operation="restart")

    async def get_operation_status(self, serial_number: str) -> Optional[TaskStatusResponse]:
        """
        查询 controllersrv 中任务的最新状态
        Query latest task status from controllersrv
        """

        response = await super().get_operation_status(serial_number)
        if response.success and isinstance(response.data, TaskStatusResponse):
            return response.data

        logger.warning(
            "Failed to fetch controllersrv task status: serial=%s, error=%s",
            serial_number,
            response.error.msg if response.error else "unknown",
        )
        return None

    def _to_controller_result(
            self,
            response: APIResponse[Optional[ServiceOperationResponse]],
            operation: str,
    ) -> ControllerSrvResult:
        """将 controllersrv 响应转换为 ControllerSrvResult / Convert controllersrv response to ControllerSrvResult"""

        data = response.data

        if isinstance(data, EnqueueSuccessResponse):
            message = data.message or f"{operation} operation accepted"
            return ControllerSrvResult(success=True, message=message)

        if isinstance(data, EnqueueErrorResponse):
            message = data.message or f"{operation} operation rejected"
            return ControllerSrvResult(success=False, message=message, error=message)

        if isinstance(data, ValidationResult):
            message = self._build_validation_message(data)
            return ControllerSrvResult(success=False, message=message, error=message)

        if response.success:
            # controllersrv 成功但未返回详细数据 / controllersrv succeeded without detail
            return ControllerSrvResult(success=True, message=f"{operation} operation accepted")

        error_message = response.error.msg or f"controllersrv {operation} request failed"
        return ControllerSrvResult(
            success=False,
            message=error_message,
            error=error_message,
        )

    @staticmethod
    def _build_validation_message(validation: ValidationResult) -> str:
        """拼接服务校验失败原因 / Build validation failure message"""

        parts: List[str] = []
        if validation.invalid_services:
            parts.append(f"Invalid services: {', '.join(validation.invalid_services)}")
        if validation.non_operable_services:
            parts.append(f"Non-operable services: {', '.join(validation.non_operable_services)}")
        if validation.valid_services and not validation.valid:
            parts.append(f"Valid subset: {', '.join(validation.valid_services)}")
        return "; ".join(parts) if parts else "Service validation failed"

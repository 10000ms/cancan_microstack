"""
服务管理 API 接口层 / Service Management API Interface Layer

提供统一的服务管理接口，供 opsbffsrv 调用 / Provides unified service management interface for opsbffsrv
"""
from linglong_web.utils import logger
from linglong_web import build_success_response
from linglong_web.utils.time import to_server_tz_iso
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.infra.service_management import (
    ServiceManagementRequest,
    ServiceManagementResponse,
    ServiceManagementAPIResponse,
)
from cancan_microstack.public.const.operation_consts import (
    OperationType,
)
from cancan_microstack.services.infrasrv.application.service_management_app import ServiceManagementApp

# 全局应用层实例 / Global application layer instance
_app = ServiceManagementApp()


def _build_service_management_response(
        response: ServiceManagementResponse,
) -> APIResponse[dict]:
    """将领域响应转换为标准 API 响应 / Convert domain response to standard API response."""

    api_response = ServiceManagementAPIResponse(
        operation_id=response.operation_id,
        status=response.status,
        service_name=response.service_name,
        message=response.message,
        result=response.result,
        error_message=response.error_message,
        # 出参统一转换为东八区，便于前端展示 / Convert timestamps to Asia/Shanghai for UI clarity
        started_at=to_server_tz_iso(response.started_at),
        completed_at=to_server_tz_iso(response.completed_at),
    )
    return build_success_response(data=api_response.model_dump())


async def start_service_handler(
        request: ServiceManagementRequest,
) -> APIResponse[dict]:
    """
    启动服务 API Handler / Start Service API Handler
    
    Args:
        request: 服务管理请求 / Service management request
    
    Returns:
        统一响应格式 / Unified response format
    """
    logger.info(
        f"[API] Received start service request: operation_id={request.operation_id}, service={request.service_name}")

    # 确保操作类型正确 / Ensure correct operation type
    request.operation_type = OperationType.START

    # 调用应用层执行操作 / Call application layer to execute operation
    response: ServiceManagementResponse = await _app.execute_service_management(request)

    return _build_service_management_response(response)


async def stop_service_handler(
        request: ServiceManagementRequest,
) -> APIResponse[dict]:
    """
    停止服务 API Handler / Stop Service API Handler
    
    Args:
        request: 服务管理请求 / Service management request
    
    Returns:
        统一响应格式 / Unified response format
    """
    logger.info(
        f"[API] Received stop service request: operation_id={request.operation_id}, service={request.service_name}")

    # 确保操作类型正确 / Ensure correct operation type
    request.operation_type = OperationType.STOP

    # 调用应用层执行操作 / Call application layer to execute operation
    response: ServiceManagementResponse = await _app.execute_service_management(request)

    return _build_service_management_response(response)


async def restart_service_handler(
        request: ServiceManagementRequest,
) -> APIResponse[dict]:
    """
    重启服务 API Handler / Restart Service API Handler
    
    Args:
        request: 服务管理请求 / Service management request
    
    Returns:
        统一响应格式 / Unified response format
    """
    logger.info(
        f"[API] Received restart service request: operation_id={request.operation_id}, service={request.service_name}")

    # 确保操作类型正确 / Ensure correct operation type
    request.operation_type = OperationType.RESTART

    # 调用应用层执行操作 / Call application layer to execute operation
    response: ServiceManagementResponse = await _app.execute_service_management(request)

    return _build_service_management_response(response)


"""
异步操作管理 API

为前端提供异步操作管理接口：
1. 异步启动/停止/重启/扩缩容/重建服务（立即返回 operation_id）
2. 查询操作状态
3. 列出操作历史

架构说明：
- opsbffsrv: 生成 operation_id，管理操作记录（通过 infrasrv），协调异步执行
- controllersrv: 纯粹的 Docker 命令执行器，同步返回结果
- infrasrv: 存储操作记录，提供查询接口
"""
from typing import (
    Optional,
)
import http

from pydantic import (
    BaseModel,
    Field,
)

from cancan_microstack.public.const.error import ErrorCode
from linglong_web import LinglongHTTPException
from cancan_microstack.public.const.operation_consts import (
    OperationType,
    InitiatedBy,
    InitiatedFrom,
)
from cancan_microstack.public.schemas.common import (
    APIResponse,
)
from cancan_microstack.public.schemas.infra.operation import (
    OperationResponse,
    OperationListResponse,
)
from cancan_microstack.public.schemas.opsbffsrv.async_ops import AsyncOperationResponse
from linglong_web import (
    build_success_response,
)
from cancan_microstack.services.opsbffsrv.application.async_operation_app import AsyncOperationApp
from cancan_microstack.services.opsbffsrv.infrastructure.api.infrasrv_api import InfraSrvApi
from linglong_web.utils import logger

# 应用层和基础设施层实例
_async_op_app = AsyncOperationApp()
_infrasrv_api = InfraSrvApi()


class AsyncOperationRequest(BaseModel):
    """异步操作请求模型"""
    service_name: str = Field(..., description="服务名称（不带 .service 后缀）")
    operation_params: dict = Field(default_factory=dict, description="操作参数")
    initiated_by: InitiatedBy = Field(default=InitiatedBy.OPSBFFSRV, description="操作发起者")


async def async_start_service_handler(
        request: AsyncOperationRequest,
) -> APIResponse[AsyncOperationResponse]:
    """异步启动服务"""
    logger.info(f"Async start service: {request.service_name}")
    result = await _async_op_app.submit_operation(
        operation_type=OperationType.START,
        service_name=request.service_name,
        operation_params=request.operation_params,
        initiated_by=request.initiated_by,
        initiated_from=InitiatedFrom.FRONTEND
    )
    return build_success_response(data=result)


async def async_stop_service_handler(
        request: AsyncOperationRequest,
) -> APIResponse[AsyncOperationResponse]:
    """异步停止服务"""
    logger.info(f"Async stop service: {request.service_name}")
    result = await _async_op_app.submit_operation(
        operation_type=OperationType.STOP,
        service_name=request.service_name,
        operation_params=request.operation_params,
        initiated_by=request.initiated_by,
        initiated_from=InitiatedFrom.FRONTEND
    )
    return build_success_response(data=result)


async def async_restart_service_handler(
        request: AsyncOperationRequest,
) -> APIResponse[AsyncOperationResponse]:
    """异步重启服务"""
    logger.info(f"Async restart service: {request.service_name}")
    result = await _async_op_app.submit_operation(
        operation_type=OperationType.RESTART,
        service_name=request.service_name,
        operation_params=request.operation_params,
        initiated_by=request.initiated_by,
        initiated_from=InitiatedFrom.FRONTEND
    )
    return build_success_response(data=result)



async def get_operation_status_handler(
        operation_id: str,
) -> APIResponse[OperationResponse]:
    """查询操作状态"""
    logger.debug(f"Query operation status: {operation_id}")
    # 使用新的 get_operation 方法（基类中定义）
    result = await _infrasrv_api.get_operation(operation_id)
    if result.success and result.data is not None:
        return build_success_response(data=result.data)

    message = result.error.msg or "Failed to query operation status"
    raise LinglongHTTPException(
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        error_code=result.error.code or ErrorCode.SYSTEM_ERROR,
    )


async def list_operations_handler(
        service_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
) -> APIResponse[OperationListResponse]:
    """列出操作历史"""
    logger.debug(f"List operations: service={service_name}, status={status}")
    result = await _infrasrv_api.list_operations(service_name, status, limit, offset)
    if result.success and result.data is not None:
        return build_success_response(data=result.data)

    message = result.error.msg or "Failed to list operations"
    raise LinglongHTTPException(
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        error_code=result.error.code or ErrorCode.SYSTEM_ERROR,
    )

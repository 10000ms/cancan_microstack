"""
内部操作管理 API

提供给 controllersrv 使用的内部接口，用于管理操作记录
"""
from typing import Optional
from datetime import datetime
import http

from pydantic import (
    BaseModel,
    Field,
)
from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_operation_op import (
    create_operation,
    get_operation_by_id,
    update_operation,
    query_operations,
    get_timeout_operations,
)
from cancan_microstack.public.schemas.infra.service_operation import (
    ServiceOperation,
    ServiceOperationCreate,
    ServiceOperationUpdate,
    ServiceOperationQuery,
)
from linglong_web.utils.time import to_server_tz_iso


def _serialize_operation(operation: Optional[ServiceOperation]) -> Optional[dict]:
    """统一序列化操作记录，确保时间字段为东八区 ISO 字符串 / Serialize operation with Asia/Shanghai timestamps."""
    if not operation:
        return None
    data = operation.model_dump()
    for field_name in ("started_at", "completed_at", "last_retry_at", "created_time", "update_time"):
        data[field_name] = to_server_tz_iso(getattr(operation, field_name, None))
    return data


class InternalOperationCreateRequest(BaseModel):
    """内部操作创建请求"""
    operation_id: str
    operation_type: str
    service_name: str
    operation_params: dict = Field(default_factory=dict)
    status: str = "pending"
    initiated_by: str = "controllersrv"
    initiated_from: str = "localhost"


class InternalOperationUpdateRequest(BaseModel):
    """内部操作更新请求"""
    operation_id: str
    status: Optional[str] = None
    started_at: Optional[str] = None  # ISO format string
    completed_at: Optional[str] = None  # ISO format string
    result: Optional[dict] = None
    error_message: Optional[str] = None


async def internal_create_operation_handler(
        request: InternalOperationCreateRequest,
) -> APIResponse[dict | None]:
    """
    内部接口：创建操作记录
    
    Args:
        request: 操作创建请求
    
    Returns:
        创建结果
    """
    operation_data = ServiceOperationCreate(
        operation_id=request.operation_id,
        operation_type=request.operation_type,
        service_name=request.service_name,
        operation_params=request.operation_params,
        status=request.status,
        initiated_by=request.initiated_by,
        initiated_from=request.initiated_from,
    )

    operation = await create_operation(operation_data)

    return build_success_response(
        data={
            "operation": _serialize_operation(operation),
        }
    )


async def internal_update_operation_handler(
        request: InternalOperationUpdateRequest,
) -> APIResponse[dict | None]:
    """
    内部接口：更新操作记录
    
    Args:
        request: 操作更新请求
    
    Returns:
        更新结果
    """
    update_data = ServiceOperationUpdate()

    if request.status:
        update_data.status = request.status

    if request.started_at:
        update_data.started_at = datetime.fromisoformat(request.started_at.replace('Z', '+00:00'))

    if request.completed_at:
        update_data.completed_at = datetime.fromisoformat(request.completed_at.replace('Z', '+00:00'))

    if request.result:
        update_data.result = request.result

    if request.error_message:
        update_data.error_message = request.error_message

    operation = await update_operation(request.operation_id, update_data)

    return build_success_response(
        data={
            "operation": _serialize_operation(operation),
        }
    )


async def internal_get_operation_handler(operation_id: str) -> APIResponse[dict | None]:
    """
    内部接口：获取操作记录
    
    Args:
        operation_id: 操作ID
    
    Returns:
        操作记录
    """
    operation = await get_operation_by_id(operation_id)

    if operation:
        return build_success_response(
            data={
                "operation": _serialize_operation(operation),
            }
        )
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.NOT_FOUND.value,
            error_code=ErrorCode.HANDLER_NOT_FOUND,
            msg=f"Operation not found: {operation_id}",
        )


async def internal_list_operations_handler(
        service_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
) -> APIResponse[dict]:
    """
    内部接口：查询操作列表
    
    Args:
        service_name: 服务名称过滤
        status: 状态过滤
        limit: 返回数量限制
    
    Returns:
        操作列表
    """
    query = ServiceOperationQuery(
        service_name=service_name,
        status=status,
        limit=limit
    )

    operations = await query_operations(query)

    return build_success_response(
        data={
            "operations": [_serialize_operation(op) for op in operations],
            "count": len(operations),
        }
    )


async def internal_check_timeouts_handler() -> APIResponse[dict]:
    """
    内部接口：检查超时操作
    
    Returns:
        超时操作列表
    """
    timeout_operations = await get_timeout_operations()

    return build_success_response(
        data={
            "timeout_operations": [_serialize_operation(op) for op in timeout_operations],
            "count": len(timeout_operations),
        }
    )

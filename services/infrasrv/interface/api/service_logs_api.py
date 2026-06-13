"""
服务行为日志查询 API - 为 opsbffsrv 提供日志查询接口
"""

from typing import Optional

from linglong_web.utils import logger
from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.error import ParamError
from cancan_microstack.services.infrasrv.application.service_logs_app import ServiceLogsApp

_service_logs_app = ServiceLogsApp()


async def get_service_logs_handler(
        service_name: Optional[str] = None,
        action_type: Optional[str] = None,
        action_status: Optional[str] = None,
        limit: int = 100,
) -> APIResponse[list[dict]]:
    """
    查询服务行为日志
    
    Args:
        service_name: 服务名称（可选）
        action_type: 操作类型（可选）
        action_status: 操作状态（可选）
        limit: 返回数量限制
    
    Returns:
        统一响应格式
    """
    logger.info(
        f"Query service logs: service_name={service_name}, "
        f"action_type={action_type}, action_status={action_status}, limit={limit}"
    )

    if limit < 1 or limit > 1000:
        raise ParamError("limit must be between 1 and 1000")

    logs = await _service_logs_app.query_logs(
        service_name=service_name,
        action_type=action_type,
        action_status=action_status,
        limit=limit
    )

    return build_success_response(data=[log.model_dump() for log in logs])

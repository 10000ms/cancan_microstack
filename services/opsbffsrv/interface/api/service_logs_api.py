"""服务行为日志查询 API / Service log query API for ops frontend."""

from typing import Optional
import http

from linglong_web.utils import logger
from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import build_success_response
from cancan_microstack.public.const.opsbffsrv_error import OpsbffsrvServiceLogsErrorCode
from cancan_microstack.public.schemas.opsbffsrv.service_logs import ServiceLogsPayload
from cancan_microstack.public.error import HTTPException
from cancan_microstack.services.opsbffsrv.application.service_logs_app import (
    ServiceLogsApp,
)

_service_logs_app = ServiceLogsApp()
_INVALID_LIMIT_MESSAGE = "Invalid input: limit must be between 1 and 1000"
_MISSING_SERVICE_NAME_MESSAGE = "Invalid input: service_name is required"


async def get_service_logs_handler(
        service_name: Optional[str] = None,
        action_type: Optional[str] = None,
        action_status: Optional[str] = None,
        limit: int = 100,
) -> APIResponse[ServiceLogsPayload]:
    """查询服务行为日志 / Query service action logs."""

    logger.info(
        "Get service logs: service_name=%s, action_type=%s, action_status=%s, limit=%s",
        service_name,
        action_type,
        action_status,
        limit,
    )

    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceLogsErrorCode.INVALID_INPUT,
            msg=_INVALID_LIMIT_MESSAGE,
        )

    payload = await _service_logs_app.get_service_logs(
        service_name=service_name,
        action_type=action_type,
        action_status=action_status,
        limit=limit,
    )

    return build_success_response(data=payload)


async def get_service_logs_by_service_handler(
        service_name: str,
        limit: int = 50,
) -> APIResponse[ServiceLogsPayload]:
    """查询指定服务的行为日志 / Query logs for a single service."""

    logger.info("Get logs for service: %s, limit=%s", service_name, limit)

    if not service_name:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceLogsErrorCode.INVALID_INPUT,
            msg=_MISSING_SERVICE_NAME_MESSAGE,
        )

    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceLogsErrorCode.INVALID_INPUT,
            msg=_INVALID_LIMIT_MESSAGE,
        )

    payload = await _service_logs_app.get_service_logs(
        service_name=service_name,
        limit=limit,
    )

    return build_success_response(data=payload)

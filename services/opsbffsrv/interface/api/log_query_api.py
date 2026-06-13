"""业务日志查询 API / Business log search API."""
import http

from linglong_web.utils import logger
from cancan_microstack.public.const.opsbffsrv_error import OpsbffsrvServiceLogsErrorCode
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.logging.log_event import (
    LogQueryRequest,
    LogQueryResponse,
)
from linglong_web import build_success_response

from cancan_microstack.services.opsbffsrv.application.logging.log_query_app import log_query_app


async def search_business_logs_handler(payload: LogQueryRequest) -> APIResponse[LogQueryResponse]:
    """查询业务日志 / Search business log documents."""
    logger.info(
        "Search business logs: services=%s range=%s -> %s",
        payload.service_names,
        payload.start_time,
        payload.end_time,
    )
    try:
        result = await log_query_app.search_logs(payload)
    except ValueError as exc:
        logger.warning("Log search validation error: %s", exc)
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceLogsErrorCode.INVALID_INPUT,
            msg=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Log search failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
            error_code=OpsbffsrvServiceLogsErrorCode.INTERNAL_ERROR,
            msg="Failed to query business logs",
        )
    return build_success_response(data=result)

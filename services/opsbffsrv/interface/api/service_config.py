"""
服务配置管理 API 接口
API handlers for service configuration management within opsbffsrv
"""
import json
from typing import (
    Any,
)

from cancan_microstack.public.schemas.common import (
    APIResponse,
)
from linglong_web import (
    build_success_response,
)
from cancan_microstack.public.const.opsbffsrv_error import OpsbffsrvServiceConfigErrorCode
from cancan_microstack.public.schemas.opsbffsrv.service_config import (
    ServiceConfigDetail,
    ServiceConfigOperationSummary,
    ServiceConfigOverview,
)
from cancan_microstack.public.error import HTTPException
import http
from cancan_microstack.services.opsbffsrv.application.service_config import ServiceConfigApp

_service_config_app = ServiceConfigApp()
_INVALID_INPUT_MESSAGE = "Invalid input"


def _normalize_conf_dict(payload: dict[str, Any]) -> dict[str, str]:
    """标准化配置请求体（单一规范）。
    Normalize config payload (single canonical shape).

    规范请求体 / Canonical payload:
    - {"conf_dict": {"KEY": "VALUE"}}
    """

    if "conf_dict" not in payload:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
            msg=_INVALID_INPUT_MESSAGE,
        )

    raw_conf = payload.get("conf_dict")

    if not isinstance(raw_conf, dict) or not raw_conf:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
            msg=_INVALID_INPUT_MESSAGE,
        )

    normalized_conf: dict[str, str] = {}
    for key, value in raw_conf.items():
        if not isinstance(key, str) or not key:
            raise HTTPException(
                status_code=http.HTTPStatus.BAD_REQUEST.value,
                error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
                msg=_INVALID_INPUT_MESSAGE,
            )

        if isinstance(value, str):
            normalized_conf[key] = value
            continue

        try:
            normalized_conf[key] = json.dumps(value, ensure_ascii=False)
        except TypeError:
            normalized_conf[key] = str(value)

    if not normalized_conf:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
            msg=_INVALID_INPUT_MESSAGE,
        )

    return normalized_conf


async def get_service_config_handler(service_name: str) -> APIResponse[ServiceConfigDetail]:
    """获取指定服务的配置 / Fetch configuration entries for a service"""
    result = await _service_config_app.get_service_config(service_name)
    return build_success_response(data=result)


async def insert_service_config_handler(
        service_name: str,
        payload: dict[str, Any],
) -> APIResponse[ServiceConfigOperationSummary]:
    """插入服务配置 / Insert new configuration entries"""

    if not service_name:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
            msg=_INVALID_INPUT_MESSAGE,
        )

    conf_dict = _normalize_conf_dict(payload)

    result = await _service_config_app.insert_service_config(service_name, conf_dict)
    return build_success_response(data=result)


async def update_service_config_handler(
        service_name: str,
        payload: dict[str, Any],
) -> APIResponse[ServiceConfigOperationSummary]:
    """更新服务配置 / Update configuration entries"""

    if not service_name:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
            msg=_INVALID_INPUT_MESSAGE,
        )

    conf_dict = _normalize_conf_dict(payload)

    result = await _service_config_app.update_service_config(service_name, conf_dict)
    return build_success_response(data=result)


async def get_all_service_configs_handler() -> APIResponse[ServiceConfigOverview]:
    """获取所有服务的配置 / Fetch configuration overview for all services"""
    result = await _service_config_app.get_all_service_configs()
    return build_success_response(data=result)


async def delete_service_config_handler(
        service_name: str,
        conf_key: str,
) -> APIResponse[ServiceConfigOperationSummary]:
    """删除服务配置项 / Delete configuration entry"""

    if not service_name or not conf_key:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            error_code=OpsbffsrvServiceConfigErrorCode.INVALID_INPUT,
            msg=_INVALID_INPUT_MESSAGE,
        )

    result = await _service_config_app.delete_service_config(service_name, conf_key)
    return build_success_response(data=result)

"""
Internal API for infrasrv
These endpoints are called by other internal services (like opsbffsrv)
Not exposed to frontend
"""
import http
from typing import Any

from linglong_web import build_success_response

from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.services.infrasrv.application.service_registry import ServiceRegistryApp

_service_registry_app = ServiceRegistryApp()


def _resolve_service_name(service_name: str | None, payload: dict[str, Any] | None) -> str:
    """
    解析 service_name 参数，兼容 query 和 JSON body
    Resolve service_name from either query param or JSON payload
    """
    if service_name:
        return service_name

    if payload and isinstance(payload.get("service_name"), str):
        service_name_from_payload = payload.get("service_name", "").strip()
        if service_name_from_payload:
            return service_name_from_payload

    raise HTTPException(
        status_code=http.HTTPStatus.BAD_REQUEST.value,
        error_code=ErrorCode.MISSING_REQUIRED_PARAM,
        msg="service_name is required",
    )


async def internal_trigger_config_push_handler(
    service_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> APIResponse[dict | None]:
    """
    内部接口：触发配置推送
    由 opsbffsrv 调用，在配置更新后触发 infrasrv 向服务实例推送新配置
    """
    resolved_service_name = _resolve_service_name(service_name=service_name, payload=payload)
    result = await _service_registry_app.push_config_to_service(resolved_service_name)
    return build_success_response(data=result)

"""
实例管理 API（Phase 4）

为前端提供实例管理接口：
1. 查询服务的所有实例
2. 查询单个实例详情
3. 查询实例统计信息
"""
from typing import Optional
import http

from linglong_web.utils import logger
from cancan_microstack.public.schemas.common import APIResponse
from linglong_web import build_success_response
from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from linglong_web import LinglongConfig
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.error import ErrorCode


async def list_service_instances_handler(
        service_name: Optional[str] = None,
        status: Optional[str] = None,
) -> APIResponse[dict | None]:
    """
    列出服务实例
    
    Args:
        service_name: 服务名称过滤（可选）
        status: 状态过滤（可选，如 running, stopped, starting）
    
    Returns:
        实例列表
    """
    logger.debug(f"List instances: service={service_name}, status={status}")

    # 调用 infrasrv 内部实例列表 API
    url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/internal/instance/list"

    params = {}
    if service_name:
        params["service_name"] = service_name
    if status:
        params["status"] = status

    resp = await http_client.get(
        url,
        params=params,
        timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
    )

    if resp and resp.status == 200:
        data = await resp.json()
        return build_success_response(data=data.get("data"))

    error_msg = f"Failed to list instances: HTTP {resp.status if resp else 'None'}"
    logger.error(error_msg)
    raise HTTPException(
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        error_code=ErrorCode.SYSTEM_ERROR,
        msg=error_msg
    )


async def get_instance_detail_handler(instance_id: str) -> APIResponse[dict | None]:
    """
    获取实例详情
    
    Args:
        instance_id: 实例ID
    
    Returns:
        实例详细信息
    """
    logger.debug(f"Get instance detail: {instance_id}")

    # 调用 infrasrv 内部实例查询 API
    url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/internal/instance/get"

    resp = await http_client.get(
        url,
        params={"instance_id": instance_id},
        timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
    )

    if resp and resp.status == 200:
        data = await resp.json()
        return build_success_response(data=data.get("data"))

    error_msg = f"Failed to get instance detail: HTTP {resp.status if resp else 'None'}"
    logger.error(error_msg)
    raise HTTPException(
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        error_code=ErrorCode.SYSTEM_ERROR,
        msg=error_msg
    )


async def get_service_instance_stats_handler(service_name: str) -> APIResponse[dict]:
    """
    获取服务的实例统计信息
    
    Args:
        service_name: 服务名称
    
    Returns:
        实例统计信息（总数、运行中、停止、健康状态等）
    """
    logger.debug(f"Get instance stats: {service_name}")

    # 调用 infrasrv 内部实例列表 API 获取所有实例
    url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/internal/instance/list"

    resp = await http_client.get(
        url,
        params={"service_name": service_name},
        timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
    )

    if resp and resp.status == 200:
        data = await resp.json()
        instances = data.get("data", {}).get("instances", [])

        # 统计信息
        stats = {
            "service_name": service_name,
            "total": len(instances),
            "by_status": {},
            "by_health": {},
            "instances": instances
        }

        # 按状态统计（支持 dict 或 Pydantic model）
        for instance in instances:
            if hasattr(instance, "get"):
                status = instance.get("status", "unknown")
                health_status = instance.get("health_status", "unknown")
            else:
                # 可能是 Pydantic model 或对象
                status = getattr(instance, "status", "unknown")
                # health_status 可能是枚举实例，要转为字符串
                hs_val = getattr(instance, "health_status", None)
                if hs_val is None:
                    health_status = "unknown"
                else:
                    try:
                        health_status = hs_val.value
                    except Exception:
                        health_status = str(hs_val)

            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_health"][health_status] = stats["by_health"].get(health_status, 0) + 1

        return build_success_response(data=stats)

    error_msg = f"Failed to get instance stats: HTTP {resp.status if resp else 'None'}"
    logger.error(error_msg)
    raise HTTPException(
        status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR.value,
        error_code=ErrorCode.SYSTEM_ERROR,
        msg=error_msg
    )

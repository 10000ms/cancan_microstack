"""
Caddy 证书管理 API 接口

提供 HTTPS 证书的 CRUD 操作、续期管理、统计等功能
"""
from typing import Optional
import http

from pydantic import BaseModel, Field

from linglong_web.utils import logger
from linglong_web import build_success_response
from linglong_web import limiter
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.caddy import CaddyCertificateCreate, CaddyCertificateUpdate
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.opsbffsrv_error import \
    OpsbffsrvCaddyRouteErrorCode as ErrorCode  # Using generic error codes or specific ones if available
from cancan_microstack.services.opsbffsrv.application.caddy.certificate_management_app import CertificateManagementApp

# 应用层实例
_cert_app = CertificateManagementApp()


class ToggleAutoRenewPayload(BaseModel):
    """切换证书自动续期请求体 / Toggle certificate auto-renew request payload"""

    enabled: bool = Field(
        ...,
        description="目标自动续期状态 / Desired auto-renew state",
    )


@limiter("20/second")
async def register_certificate_handler(cert_data: CaddyCertificateCreate) -> APIResponse[dict]:
    """
    注册证书
    
    Args:
        cert_data: 证书数据
    
    Returns:
        统一响应格式
    """
    logger.info(f"注册证书: domain={cert_data.domain}")
    result = await _cert_app.register_certificate(cert_data)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=result.get("message", "注册证书失败"),
            detail=str(result)
        )


@limiter("20/second")
async def update_certificate_handler(cert_id: int, cert_data: CaddyCertificateUpdate) -> APIResponse[dict]:
    """
    更新证书信息
    
    Args:
        cert_id: 证书ID
        cert_data: 更新数据
    
    Returns:
        统一响应格式
    """
    logger.info(f"更新证书: id={cert_id}")
    result = await _cert_app.update_certificate(cert_id, cert_data)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=result.get("message", "更新证书失败"),
            detail=str(result)
        )


@limiter("20/second")
async def get_certificate_handler(cert_id: int) -> APIResponse[dict]:
    """
    获取证书详情
    
    Args:
        cert_id: 证书ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"获取证书: id={cert_id}")
    cert = await _cert_app.get_certificate(cert_id)

    if cert:
        return build_success_response(data=cert.model_dump(exclude={"private_key_pem"}))
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.NOT_FOUND.value,
            msg="证书不存在"
        )


@limiter("20/second")
async def list_certificates_handler(
        domain: Optional[str] = None,
        status: Optional[str] = None
) -> APIResponse[dict]:
    """
    列出证书（支持过滤）
    
    Args:
        domain: 域名过滤
        status: 状态过滤（active/expiring/expired/renewing/revoked）
    
    Returns:
        统一响应格式
    """
    logger.info(f"列出证书: domain={domain}, status={status}")
    certs = await _cert_app.list_certificates(domain=domain, status=status)

    return build_success_response(data={
        "certificates": [c.model_dump(exclude={"private_key_pem"}) for c in certs],
        "total": len(certs)
    })


@limiter("10/second")
async def delete_certificate_handler(cert_id: int) -> APIResponse[dict]:
    """
    删除证书
    
    Args:
        cert_id: 证书ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"删除证书: id={cert_id}")
    result = await _cert_app.delete_certificate(cert_id)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=result.get("message", "删除证书失败"),
            detail=str(result)
        )


@limiter("5/second")
async def renew_certificate_handler(cert_id: int) -> APIResponse[dict]:
    """
    手动续期证书
    
    Args:
        cert_id: 证书ID
    
    Returns:
        统一响应格式
    """
    logger.info(f"手动续期证书: id={cert_id}")
    result = await _cert_app.renew_certificate_manually(cert_id)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=result.get("message", "续期证书失败"),
            detail=str(result)
        )


@limiter("10/second")
async def toggle_auto_renew_handler(cert_id: int, payload: ToggleAutoRenewPayload) -> APIResponse[dict]:
    """
    切换证书自动续期状态

    Args:
        cert_id: 证书ID
        payload: 请求体，包含目标自动续期状态 enabled

    Returns:
        统一响应格式
    """
    logger.info(f"切换证书自动续期: id={cert_id}, enabled={payload.enabled}")
    result = await _cert_app.toggle_auto_renew(cert_id, payload.enabled)

    if result.get("status") == "success":
        return build_success_response(data=result)
    else:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST.value,
            msg=result.get("message", "切换自动续期失败"),
            detail=str(result)
        )


@limiter("20/second")
async def list_expiring_certificates_handler(days: int = 30) -> APIResponse[dict]:
    """
    列出即将过期的证书
    
    Args:
        days: 天数阈值（默认30天）
    
    Returns:
        统一响应格式
    """
    logger.info(f"列出即将过期证书: days={days}")
    certs = await _cert_app.list_expiring_certificates(days)

    return build_success_response(data={
        "expiring_certificates": [c.model_dump(exclude={"private_key_pem"}) for c in certs],
        "total": len(certs),
        "days_threshold": days
    })


@limiter("20/second")
async def get_certificate_statistics_handler() -> APIResponse[dict]:
    """
    获取证书统计信息
    
    Returns:
        统一响应格式
    """
    logger.info("获取证书统计信息")
    stats = await _cert_app.get_certificate_statistics()

    return build_success_response(data=stats)

"""
Caddy HTTPS 证书管理应用服务
协调证书生命周期管理的业务流程。

现状说明（重要）：
- ACME 自动续订 **尚未实现**。本服务没有集成 certbot / acme.sh 等 ACME 客户端，
  无法真正申请 / 续订证书。因此 `renew_certificate_manually` 与
  `check_and_renew_expiring_certificates` 一律 **不会** 把证书标记为续订成功，
  而是返回 / 抛出明确的"未实现"错误，避免把过期证书假装成有效证书。
- `mark_expired_certificates` 仍保留：把已过期证书标为 expired 是诚实且有用的。
"""
import http
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import datetime
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyCertificate
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.const.error import ErrorCode
from cancan_microstack.services.opsbffsrv.domain.caddy.certificate_management import CertificateManagementDomain

# ACME 自动续订未实现时统一返回的提示信息 / Message returned when ACME auto-renew is not implemented
_ACME_NOT_IMPLEMENTED_MSG = (
    "ACME 自动续订未实现，请手动续订证书 / "
    "ACME auto-renewal is not implemented; please renew the certificate manually"
)


class CertificateManagementApp:
    """证书管理应用服务"""

    def __init__(self):
        self.domain = CertificateManagementDomain()

    async def register_certificate(self, cert: CaddyCertificate) -> Dict[str, Any]:
        """
        注册证书
        
        Args:
            cert: 证书对象
            
        Returns:
            结果字典
        """
        logger.info(f"Registering certificate for domain: {cert.domain}")

        try:
            registered_cert = await self.domain.register_new_certificate(cert)

            return {
                "status": "success",
                "certificate": registered_cert
            }
        except ValueError as e:
            logger.warning(f"Certificate registration failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error registering certificate: {e}", exc_info=True)
            return {
                "status": "error",
                "error": "Internal server error"
            }

    async def renew_certificate_manually(self, cert_id: int) -> Dict[str, Any]:
        """
        手动续期证书

        现状：ACME 证书申请逻辑 **尚未实现**（未集成 certbot / acme.sh 等客户端）。
        因此本方法不会真正续订证书，也 **绝不** 把未续订的证书标记为 active /
        续订成功（历史上这里写死 success=True，会把过期证书"洗"成有效，已移除）。
        在 ACME 集成落地前，统一抛出"未实现"错误，由调用方提示用户手动续订。

        Args:
            cert_id: 证书 ID

        Raises:
            HTTPException: 证书不存在（404）；或 ACME 自动续订未实现（501）

        Returns:
            结果字典（当前实现总是抛异常，不会正常返回）
        """
        logger.info(f"Manually renewing certificate: {cert_id}")

        # 先确认证书存在，给出更准确的错误
        cert = await self.domain.get_certificate_details(cert_id)
        if not cert:
            raise HTTPException(
                status_code=http.HTTPStatus.NOT_FOUND.value,
                error_code=ErrorCode.HANDLER_NOT_FOUND,
                msg="Certificate not found",
            )

        # ACME 自动续订未实现：诚实失败，不记录任何"续订成功"结果。
        # ACME auto-renewal not implemented: fail honestly, never record a fake success.
        logger.warning(
            "Certificate renewal requested for cert_id=%s but ACME auto-renewal is not implemented",
            cert_id,
        )
        raise HTTPException(
            status_code=http.HTTPStatus.NOT_IMPLEMENTED.value,
            error_code=ErrorCode.SYSTEM_ERROR,
            msg=_ACME_NOT_IMPLEMENTED_MSG,
        )

    async def check_and_renew_expiring_certificates(self) -> Dict[str, Any]:
        """
        检查并续期即将过期的证书

        现状：此方法本应由调度器定期调用，但 **目前没有任何调度器调用它**；
        且 ACME 自动续订 **尚未实现**。因此它只能 **识别** 出哪些证书需要续订，
        但 **无法真正续订**，更 **绝不** 假装续订成功（历史实现会把过期证书
        洗成有效，已移除）。返回摘要中 renewed 恒为 0，needs_manual_renewal
        给出需人工续订的证书数量。

        Returns:
            续期结果摘要（renewed 恒为 0；不抛异常，便于将来挂调度器时观测）
        """
        logger.info("Checking for expiring certificates...")

        try:
            # 获取需要续期的证书
            certs_to_renew = await self.domain.get_certificates_needing_renewal()

            if not certs_to_renew:
                logger.info("No certificates need renewal")
                return {
                    "status": "success",
                    "message": "No certificates need renewal",
                    "renewed": 0,
                    "needs_manual_renewal": 0,
                }

            # ACME 未实现：只识别、不续订、不假成功
            # ACME not implemented: detect only, do not renew, never fake success
            logger.warning(
                "Found %s certificates needing renewal, but ACME auto-renewal is not implemented; "
                "manual renewal required",
                len(certs_to_renew),
            )

            return {
                "status": "success",
                "message": (
                    f"{len(certs_to_renew)} certificate(s) need renewal but ACME auto-renewal "
                    f"is not implemented; manual renewal required"
                ),
                "renewed": 0,
                "needs_manual_renewal": len(certs_to_renew),
            }
        except Exception as e:
            logger.error(f"Error in auto-renewal process: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def mark_expired_certificates(self) -> Dict[str, Any]:
        """
        标记过期证书

        把已过期的证书状态标记为 expired —— 这是诚实且有用的操作（与"续订"无关，
        不涉及 ACME），保留。

        现状：此方法本应由调度器定期调用，但 **目前没有任何调度器调用它**；
        如需生效，需在外部接入定时调度。

        Returns:
            标记结果
        """
        logger.info("Marking expired certificates...")

        try:
            count = await self.domain.check_and_mark_expired_certificates()

            return {
                "status": "success",
                "message": f"Marked {count} certificates as expired"
            }
        except Exception as e:
            logger.error(f"Error marking expired certificates: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def update_certificate(self, cert_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新证书信息
        
        Args:
            cert_id: 证书 ID
            data: 更新数据
            
        Returns:
            结果字典
        """
        logger.info(f"Updating certificate: {cert_id}")

        try:
            updated_cert = await self.domain.update_certificate_info(cert_id, data)

            if not updated_cert:
                return {
                    "status": "error",
                    "error": "Certificate not found"
                }

            return {
                "status": "success",
                "certificate": updated_cert
            }
        except Exception as e:
            logger.error(f"Error updating certificate: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def toggle_auto_renew(self, cert_id: int, enabled: bool) -> Dict[str, Any]:
        """
        切换证书自动续期状态
        
        Args:
            cert_id: 证书 ID
            enabled: 是否启用
            
        Returns:
            结果字典
        """
        logger.info(f"Toggling auto-renew for certificate {cert_id} to {enabled}")

        try:
            updated_cert = await self.domain.toggle_auto_renew(cert_id, enabled)

            if not updated_cert:
                return {
                    "status": "error",
                    "error": "Certificate not found"
                }

            return {
                "status": "success",
                "certificate": updated_cert
            }
        except Exception as e:
            logger.error(f"Error toggling auto-renew: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def delete_certificate(self, cert_id: int) -> Dict[str, Any]:
        """
        删除证书
        
        Args:
            cert_id: 证书 ID
            
        Returns:
            结果字典
        """
        logger.info(f"Deleting certificate: {cert_id}")

        try:
            success = await self.domain.remove_certificate(cert_id)

            if not success:
                return {
                    "status": "error",
                    "error": "Certificate not found or deletion failed"
                }

            return {
                "status": "success",
                "message": "Certificate deleted successfully"
            }
        except Exception as e:
            logger.error(f"Error deleting certificate: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_certificate(self, cert_id: int) -> Optional[CaddyCertificate]:
        """
        获取证书详情
        
        Args:
            cert_id: 证书 ID
            
        Returns:
            证书对象或 None
        """
        return await self.domain.get_certificate_details(cert_id)

    async def get_certificate_by_domain(self, domain: str) -> Optional[CaddyCertificate]:
        """
        根据域名获取证书
        
        Args:
            domain: 域名
            
        Returns:
            证书对象或 None
        """
        return await self.domain.get_certificate_by_domain_name(domain)

    async def list_all_certificates(self, filters: Optional[Dict[str, Any]] = None) -> List[CaddyCertificate]:
        """
        列出所有证书
        
        Args:
            filters: 过滤条件
            
        Returns:
            证书列表
        """
        return await self.domain.list_certificates(filters)

    async def list_active_certificates(self) -> List[CaddyCertificate]:
        """
        列出所有激活的证书
        
        Returns:
            证书列表
        """
        return await self.domain.list_active_certificates()

    async def list_expiring_certificates(self, days: int = 30) -> List[CaddyCertificate]:
        """
        列出即将过期的证书
        
        Args:
            days: 多少天内过期
            
        Returns:
            证书列表
        """
        return await self.domain.list_expiring_certificates(days)

    async def get_certificate_statistics(self) -> Dict[str, int]:
        """
        获取证书统计信息
        
        Returns:
            统计信息字典
        """
        return await self.domain.get_certificate_statistics_summary()

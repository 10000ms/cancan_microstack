"""
Caddy HTTPS 证书管理领域服务
包含证书生命周期管理的核心业务逻辑
"""
from typing import (
    List,
    Optional,
    Dict,
    Any,
)
from datetime import datetime

from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyCertificate
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_certificate import (
    get_certificate_by_id,
    get_certificate_by_domain,
    get_all_certificates,
    get_active_certificates,
    get_expiring_certificates,
    get_expired_certificates,
    get_auto_renew_certificates,
    upsert_certificate,
    update_certificate,
    record_renew_attempt,
    mark_certificate_expired,
    enable_auto_renew,
    disable_auto_renew,
    delete_certificate,
    get_certificate_statistics,
)


class CertificateManagementDomain:
    """证书管理领域服务"""

    async def register_new_certificate(self, cert: CaddyCertificate) -> CaddyCertificate:
        """
        注册新证书
        
        业务规则：
        1. 域名必须唯一（或使用 upsert 更新）
        2. 过期时间必须晚于当前时间
        3. 续期提前天数合理（7-90 天）
        
        Args:
            cert: 证书对象
            
        Returns:
            创建后的证书对象
        """
        logger.info(f"Registering new certificate for domain: {cert.domain}")

        # 业务规则验证
        await self._validate_certificate_create(cert)

        # 使用 upsert 避免域名冲突
        db_cert = await upsert_certificate(cert)
        logger.info(f"Certificate registered for domain: {db_cert.domain}")

        return db_cert

    async def renew_certificate(self, cert_id: int) -> Optional[CaddyCertificate]:
        """
        续期证书
        
        这是业务流程的核心方法，实际的证书申请由应用层调用 ACME 客户端完成
        领域层只负责记录续期尝试和更新状态
        
        Args:
            cert_id: 证书 ID
            
        Returns:
            更新后的证书对象或 None
        """
        logger.info(f"Initiating certificate renewal for ID: {cert_id}")

        # 验证证书存在
        existing_cert = await get_certificate_by_id(cert_id)
        if not existing_cert:
            logger.warning(f"Certificate not found: {cert_id}")
            return None

        # 记录续期尝试（应用层会调用此方法记录结果）
        return existing_cert

    async def check_and_mark_expired_certificates(self) -> int:
        """
        检查并标记过期证书
        
        业务规则：扫描所有证书，将已过期但状态不是 'expired' 的证书标记为过期
        
        Returns:
            标记为过期的证书数量
        """
        logger.info("Checking for expired certificates")

        expired_certs = await get_expired_certificates()
        count = 0

        for cert in expired_certs:
            await mark_certificate_expired(cert.id)
            logger.info(f"Marked certificate as expired: {cert.domain}")
            count += 1

        logger.info(f"Marked {count} certificates as expired")
        return count

    async def get_certificates_needing_renewal(self) -> List[CaddyCertificate]:
        """
        获取需要续期的证书列表
        
        业务规则：
        1. auto_renew = True
        2. status = 'active'
        3. 距离过期时间 <= renew_before_days
        
        Returns:
            需要续期的证书列表
        """
        logger.info("Fetching certificates needing renewal")
        return await get_auto_renew_certificates()

    async def update_certificate_info(self, cert_id: int, data: Dict[str, Any]) -> Optional[CaddyCertificate]:
        """
        更新证书信息
        
        Args:
            cert_id: 证书 ID
            data: 更新数据
            
        Returns:
            更新后的证书对象或 None
        """
        logger.info(f"Updating certificate: {cert_id}")

        # 验证证书存在
        existing_cert = await get_certificate_by_id(cert_id)
        if not existing_cert:
            logger.warning(f"Certificate not found: {cert_id}")
            return None

        # 更新数据库记录
        updated_cert = await update_certificate(cert_id, data)

        if updated_cert:
            logger.info(f"Certificate updated: {cert_id}")

        return updated_cert

    async def toggle_auto_renew(self, cert_id: int, enabled: bool) -> Optional[CaddyCertificate]:
        """
        切换证书自动续期状态
        
        Args:
            cert_id: 证书 ID
            enabled: 是否启用
            
        Returns:
            更新后的证书对象或 None
        """
        logger.info(f"Toggling auto-renew for certificate {cert_id} to: {enabled}")

        if enabled:
            updated_cert = await enable_auto_renew(cert_id)
        else:
            updated_cert = await disable_auto_renew(cert_id)

        return updated_cert

    async def record_renewal_result(self, cert_id: int, success: bool, error: Optional[str] = None) -> Optional[
        CaddyCertificate]:
        """
        记录续期结果
        
        Args:
            cert_id: 证书 ID
            success: 是否成功
            error: 错误信息（如果失败）
            
        Returns:
            更新后的证书对象或 None
        """
        logger.info(f"Recording renewal result for certificate {cert_id}: success={success}")
        return await record_renew_attempt(cert_id, success, error)

    async def remove_certificate(self, cert_id: int) -> bool:
        """
        删除证书
        
        Args:
            cert_id: 证书 ID
            
        Returns:
            是否删除成功
        """
        logger.info(f"Removing certificate: {cert_id}")

        # 验证证书存在
        existing_cert = await get_certificate_by_id(cert_id)
        if not existing_cert:
            logger.warning(f"Certificate not found: {cert_id}")
            return False

        # 删除数据库记录
        success = await delete_certificate(cert_id)

        if success:
            logger.info(f"Certificate removed: {cert_id}")

        return success

    async def get_certificate_details(self, cert_id: int) -> Optional[CaddyCertificate]:
        """
        获取证书详情
        
        Args:
            cert_id: 证书 ID
            
        Returns:
            证书对象或 None
        """
        return await get_certificate_by_id(cert_id)

    async def get_certificate_by_domain_name(self, domain: str) -> Optional[CaddyCertificate]:
        """
        根据域名获取证书
        
        Args:
            domain: 域名
            
        Returns:
            证书对象或 None
        """
        return await get_certificate_by_domain(domain)

    async def list_certificates(self, filters: Optional[Dict[str, Any]] = None) -> List[CaddyCertificate]:
        """
        列出证书
        
        Args:
            filters: 过滤条件
            
        Returns:
            证书列表
        """
        return await get_all_certificates(filters)

    async def list_active_certificates(self) -> List[CaddyCertificate]:
        """
        列出所有激活的证书
        
        Returns:
            激活证书列表
        """
        return await get_active_certificates()

    async def list_expiring_certificates(self, days: int = 30) -> List[CaddyCertificate]:
        """
        列出即将过期的证书
        
        Args:
            days: 多少天内过期
            
        Returns:
            即将过期的证书列表
        """
        return await get_expiring_certificates(days)

    async def get_certificate_statistics_summary(self) -> Dict[str, int]:
        """
        获取证书统计摘要
        
        Returns:
            统计信息字典
        """
        return await get_certificate_statistics()

    async def _validate_certificate_create(self, cert: CaddyCertificate):
        """
        验证证书创建的业务规则
        
        Args:
            cert: 证书对象
            
        Raises:
            ValueError: 业务规则违反
        """
        # 验证域名格式
        if not self._is_valid_domain(cert.domain):
            raise ValueError(f"Invalid domain format: {cert.domain}")

        # 验证过期时间
        if cert.expires_at and cert.expires_at <= datetime.utcnow():
            raise ValueError("Certificate expiration time must be in the future")

        # 验证续期提前天数
        if cert.renew_before_days < 7 or cert.renew_before_days > 90:
            raise ValueError(f"Renew before days must be between 7 and 90: {cert.renew_before_days}")

        # 验证 ACME 提供商
        valid_providers = ['letsencrypt', 'letsencrypt-staging', 'zerossl', 'buypass']
        if cert.acme_provider not in valid_providers:
            raise ValueError(f"Invalid ACME provider: {cert.acme_provider}. Must be one of {valid_providers}")

        # 验证 ACME 挑战类型
        valid_challenges = ['http-01', 'dns-01', 'tls-alpn-01']
        if cert.acme_challenge_type not in valid_challenges:
            raise ValueError(
                f"Invalid ACME challenge type: {cert.acme_challenge_type}. Must be one of {valid_challenges}")

    def _is_valid_domain(self, domain: str) -> bool:
        """
        验证域名格式
        
        Args:
            domain: 域名字符串
            
        Returns:
            是否为有效域名
        """
        import re
        # 简单的域名验证正则（支持通配符）
        pattern = r'^(\*\.)?([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

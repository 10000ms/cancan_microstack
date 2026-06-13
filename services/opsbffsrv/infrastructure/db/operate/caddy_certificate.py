"""
Caddy 证书表的数据库操作函数
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.caddy import CaddyCertificate
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.caddy_certificate_tbl import CaddyCertificateTbl


async def get_certificate_by_id(cert_id: int) -> Optional[CaddyCertificate]:
    """
    根据 ID 查询证书
    
    Args:
        cert_id: 证书 ID
        
    Returns:
        证书对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyCertificateTbl).where(CaddyCertificateTbl.id == cert_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyCertificate.model_validate(row, from_attributes=True) if row else None


async def get_certificate_by_domain(domain: str) -> Optional[CaddyCertificate]:
    """
    根据域名查询证书
    
    Args:
        domain: 域名
        
    Returns:
        证书对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyCertificateTbl).where(CaddyCertificateTbl.domain == domain)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyCertificate.model_validate(row, from_attributes=True) if row else None


async def get_all_certificates(filters: Optional[Dict[str, Any]] = None) -> List[CaddyCertificate]:
    """
    查询所有证书（支持动态过滤）
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        证书对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyCertificateTbl)

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyCertificateTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyCertificateTbl, key) == value)

            stmt = stmt.order_by(CaddyCertificateTbl.created_time.desc())
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyCertificate.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_active_certificates() -> List[CaddyCertificate]:
    """
    查询所有激活的证书
    
    Returns:
        证书对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyCertificateTbl).where(
                CaddyCertificateTbl.status == 'active'
            ).order_by(CaddyCertificateTbl.expires_at)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyCertificate.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_expiring_certificates(days: int = 30) -> List[CaddyCertificate]:
    """
    查询即将过期的证书
    
    Args:
        days: 多少天内过期
        
    Returns:
        证书对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            expiry_threshold = datetime.utcnow() + timedelta(days=days)
            stmt = select(CaddyCertificateTbl).where(
                and_(
                    CaddyCertificateTbl.status == 'active',
                    CaddyCertificateTbl.expires_at <= expiry_threshold,
                    CaddyCertificateTbl.expires_at > datetime.utcnow()
                )
            ).order_by(CaddyCertificateTbl.expires_at)
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyCertificate.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_expired_certificates() -> List[CaddyCertificate]:
    """
    查询已过期的证书
    
    Returns:
        证书对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyCertificateTbl).where(
                and_(
                    CaddyCertificateTbl.expires_at <= datetime.utcnow(),
                    CaddyCertificateTbl.status != 'expired'
                )
            ).order_by(CaddyCertificateTbl.expires_at.desc())
            rows = list((await session.execute(stmt)).scalars().all())
            return [CaddyCertificate.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def get_auto_renew_certificates() -> List[CaddyCertificate]:
    """
    查询需要自动续期的证书
    
    Returns:
        证书对象列表
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(CaddyCertificateTbl).where(
                and_(
                    CaddyCertificateTbl.auto_renew == True,
                    CaddyCertificateTbl.status == 'active'
                )
            ).order_by(CaddyCertificateTbl.expires_at)
            rows = list((await session.execute(stmt)).scalars().all())

            # 过滤出需要续期的证书（在 renew_before_days 天内过期）
            result = []
            now = datetime.utcnow()
            for row in rows:
                if row.expires_at:
                    days_until_expiry = (row.expires_at - now).days
                    if days_until_expiry <= row.renew_before_days:
                        result.append(CaddyCertificate.model_validate(row, from_attributes=True))

            return result


async def create_certificate(cert: CaddyCertificate) -> CaddyCertificate:
    """
    创建新证书
    
    Args:
        cert: 证书对象
        
    Returns:
        创建后的证书对象
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(CaddyCertificateTbl).values(
                **cert.model_dump(exclude={'id', 'created_time', 'update_time'})
            ).returning(CaddyCertificateTbl)
            row = (await session.execute(stmt)).scalar_one()
            return CaddyCertificate.model_validate(row, from_attributes=True)


async def upsert_certificate(cert: CaddyCertificate) -> CaddyCertificate:
    """
    插入或更新证书（基于域名唯一约束）
    
    Args:
        cert: 证书对象
        
    Returns:
        创建/更新后的证书对象
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            values = cert.model_dump(exclude={'id', 'created_time', 'update_time'})
            stmt = insert(CaddyCertificateTbl).values(**values)

            # PostgreSQL UPSERT: 冲突时更新所有字段
            stmt = stmt.on_conflict_do_update(
                index_elements=['domain'],
                set_={
                    'alt_domains': stmt.excluded.alt_domains,
                    'certificate_pem': stmt.excluded.certificate_pem,
                    'private_key_pem': stmt.excluded.private_key_pem,
                    'issuer': stmt.excluded.issuer,
                    'issued_at': stmt.excluded.issued_at,
                    'expires_at': stmt.excluded.expires_at,
                    'auto_renew': stmt.excluded.auto_renew,
                    'renew_before_days': stmt.excluded.renew_before_days,
                    'status': stmt.excluded.status,
                    'last_renew_attempt': stmt.excluded.last_renew_attempt,
                    'last_renew_success': stmt.excluded.last_renew_success,
                    'renew_error': stmt.excluded.renew_error,
                    'acme_provider': stmt.excluded.acme_provider,
                    'acme_email': stmt.excluded.acme_email,
                    'acme_challenge_type': stmt.excluded.acme_challenge_type,
                    'certificate_metadata': stmt.excluded.certificate_metadata,
                }
            ).returning(CaddyCertificateTbl)

            row = (await session.execute(stmt)).scalar_one()
            return CaddyCertificate.model_validate(row, from_attributes=True)


async def update_certificate(cert_id: int, data: Dict[str, Any]) -> Optional[CaddyCertificate]:
    """
    更新证书
    
    Args:
        cert_id: 证书 ID
        data: 更新数据字典
        
    Returns:
        更新后的证书对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(CaddyCertificateTbl).where(
                CaddyCertificateTbl.id == cert_id
            ).values(**data).returning(CaddyCertificateTbl)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyCertificate.model_validate(row, from_attributes=True) if row else None


async def update_certificate_by_domain(domain: str, data: Dict[str, Any]) -> Optional[CaddyCertificate]:
    """
    根据域名更新证书
    
    Args:
        domain: 域名
        data: 更新数据字典
        
    Returns:
        更新后的证书对象或 None
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(CaddyCertificateTbl).where(
                CaddyCertificateTbl.domain == domain
            ).values(**data).returning(CaddyCertificateTbl)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return CaddyCertificate.model_validate(row, from_attributes=True) if row else None


async def update_certificate_status(cert_id: int, status: str, error: Optional[str] = None) -> Optional[
    CaddyCertificate]:
    """
    更新证书状态
    
    Args:
        cert_id: 证书 ID
        status: 新状态（pending/active/expired/revoked）
        error: 错误信息（可选）
        
    Returns:
        更新后的证书对象或 None
    """
    data = {"status": status}
    if error:
        data["renew_error"] = error
    return await update_certificate(cert_id, data)


async def record_renew_attempt(cert_id: int, success: bool, error: Optional[str] = None) -> Optional[CaddyCertificate]:
    """
    记录续期尝试
    
    Args:
        cert_id: 证书 ID
        success: 是否成功
        error: 错误信息（如果失败）
        
    Returns:
        更新后的证书对象或 None
    """
    data = {
        "last_renew_attempt": datetime.utcnow()
    }

    if success:
        data["last_renew_success"] = datetime.utcnow()
        data["renew_error"] = None
        data["status"] = "active"
    else:
        data["renew_error"] = error

    return await update_certificate(cert_id, data)


async def mark_certificate_expired(cert_id: int) -> Optional[CaddyCertificate]:
    """
    标记证书为已过期
    
    Args:
        cert_id: 证书 ID
        
    Returns:
        更新后的证书对象或 None
    """
    return await update_certificate(cert_id, {"status": "expired"})


async def enable_auto_renew(cert_id: int) -> Optional[CaddyCertificate]:
    """
    启用自动续期
    
    Args:
        cert_id: 证书 ID
        
    Returns:
        更新后的证书对象或 None
    """
    return await update_certificate(cert_id, {"auto_renew": True})


async def disable_auto_renew(cert_id: int) -> Optional[CaddyCertificate]:
    """
    禁用自动续期
    
    Args:
        cert_id: 证书 ID
        
    Returns:
        更新后的证书对象或 None
    """
    return await update_certificate(cert_id, {"auto_renew": False})


async def delete_certificate(cert_id: int) -> bool:
    """
    删除证书
    
    Args:
        cert_id: 证书 ID
        
    Returns:
        是否删除成功
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyCertificateTbl).where(CaddyCertificateTbl.id == cert_id)
            result = await session.execute(stmt)
            return result.rowcount > 0


async def delete_certificate_by_domain(domain: str) -> bool:
    """
    根据域名删除证书
    
    Args:
        domain: 域名
        
    Returns:
        是否删除成功
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(CaddyCertificateTbl).where(CaddyCertificateTbl.domain == domain)
            result = await session.execute(stmt)
            return result.rowcount > 0


async def count_certificates(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    统计证书数量
    
    Args:
        filters: 过滤条件字典
        
    Returns:
        证书数量
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(func.count(CaddyCertificateTbl.id))

            # 动态添加查询条件
            if filters:
                for key, value in filters.items():
                    if hasattr(CaddyCertificateTbl, key) and value is not None:
                        stmt = stmt.where(getattr(CaddyCertificateTbl, key) == value)

            count = (await session.execute(stmt)).scalar_one()
            return count


async def get_certificate_statistics() -> Dict[str, int]:
    """
    获取证书统计信息
    
    Returns:
        统计信息字典
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            # 总证书数
            total_stmt = select(func.count(CaddyCertificateTbl.id))
            total = (await session.execute(total_stmt)).scalar_one()

            # 激活证书数
            active_stmt = select(func.count(CaddyCertificateTbl.id)).where(CaddyCertificateTbl.status == 'active')
            active = (await session.execute(active_stmt)).scalar_one()

            # 过期证书数
            expired_stmt = select(func.count(CaddyCertificateTbl.id)).where(CaddyCertificateTbl.status == 'expired')
            expired = (await session.execute(expired_stmt)).scalar_one()

            # 即将过期证书数（30天内）
            expiring_threshold = datetime.utcnow() + timedelta(days=30)
            expiring_stmt = select(func.count(CaddyCertificateTbl.id)).where(
                and_(
                    CaddyCertificateTbl.status == 'active',
                    CaddyCertificateTbl.expires_at <= expiring_threshold,
                    CaddyCertificateTbl.expires_at > datetime.utcnow()
                )
            )
            expiring = (await session.execute(expiring_stmt)).scalar_one()

            # 自动续期证书数
            auto_renew_stmt = select(func.count(CaddyCertificateTbl.id)).where(CaddyCertificateTbl.auto_renew == True)
            auto_renew = (await session.execute(auto_renew_stmt)).scalar_one()

            return {
                "total": total,
                "active": active,
                "expired": expired,
                "expiring_soon": expiring,
                "auto_renew_enabled": auto_renew
            }

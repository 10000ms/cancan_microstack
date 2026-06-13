"""
Caddy HTTPS 证书管理表 ORM 模型
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    SmallInteger,
    TIMESTAMP,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from linglong_web import TableBase


class CaddyCertificateTbl(TableBase):
    """Caddy HTTPS 证书管理表"""
    __tablename__ = 'caddy_certificate_tbl'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 域名信息
    domain = Column(String(255), nullable=False, unique=True)
    alt_domains = Column(ARRAY(Text))

    # 证书信息
    certificate_pem = Column(Text)
    private_key_pem = Column(Text)
    issuer = Column(String(255))

    # 证书时间
    issued_at = Column(TIMESTAMP(timezone=True))
    expires_at = Column(TIMESTAMP(timezone=True))
    auto_renew = Column(Boolean, default=True)
    renew_before_days = Column(Integer, default=30)

    # 证书状态
    status = Column(String(50), default='pending')
    last_renew_attempt = Column(TIMESTAMP(timezone=True))
    last_renew_success = Column(TIMESTAMP(timezone=True))
    renew_error = Column(Text)

    # ACME 配置
    acme_provider = Column(String(100), default='letsencrypt')
    acme_email = Column(String(255))
    acme_challenge_type = Column(String(50), default='http-01')

    # 元数据
    certificate_metadata = Column(JSONB, default={})

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"CaddyCertificateTbl(id={self.id}, domain={self.domain}, status={self.status})"

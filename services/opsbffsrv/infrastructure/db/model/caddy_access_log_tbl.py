"""
Caddy 访问日志表 ORM 模型
"""
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    SmallInteger,
    TIMESTAMP,
    DECIMAL,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from linglong_web import TableBase


class CaddyAccessLogTbl(TableBase):
    """Caddy 访问日志表（包含 IP 地理位置信息）"""
    __tablename__ = 'caddy_access_log_tbl'

    # 主键（使用 BIGINT）
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 请求基本信息
    request_id = Column(String(50), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.current_timestamp())

    # 客户端信息
    client_ip = Column(String(50), nullable=False)
    client_port = Column(Integer)
    user_agent = Column(Text)
    referer = Column(Text)

    # IP 地理位置信息
    country = Column(String(100))
    country_code = Column(String(10))
    region = Column(String(100))
    city = Column(String(100))
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    timezone = Column(String(50))
    isp = Column(String(200))

    # 请求信息
    method = Column(String(10), nullable=False)
    protocol = Column(String(20))
    host = Column(String(255))
    path = Column(Text, nullable=False)
    query_string = Column(Text)

    # 路由和服务信息
    matched_route = Column(String(100))
    upstream_service = Column(String(100))
    upstream_host = Column(String(100))
    upstream_port = Column(Integer)

    # 响应信息
    status_code = Column(Integer, nullable=False)
    response_size = Column(BigInteger)
    response_time = Column(Integer)

    # WAF 信息
    waf_action = Column(String(50))
    waf_rule_id = Column(String(100))
    waf_score = Column(Integer)

    # 限流信息
    rate_limited = Column(Boolean, default=False)
    rate_limit_rule = Column(String(100))

    # TLS 信息
    tls_version = Column(String(20))
    tls_cipher = Column(String(100))

    # 元数据
    log_metadata = Column(JSONB, default={})

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"CaddyAccessLogTbl(id={self.id}, client_ip={self.client_ip}, path={self.path}, status={self.status_code})"

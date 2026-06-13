"""
Caddy 统计数据表 ORM 模型
"""
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    SmallInteger,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from linglong_web import TableBase


class CaddyStatsTbl(TableBase):
    """Caddy 统计数据表（聚合统计）"""
    __tablename__ = 'caddy_stats_tbl'

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 时间维度
    stat_time = Column(TIMESTAMP(timezone=True), nullable=False)
    stat_period = Column(String(20), nullable=False)

    # 维度信息
    dimension_type = Column(String(50), nullable=False)
    dimension_value = Column(String(255))

    # 请求统计
    total_requests = Column(BigInteger, default=0)
    success_requests = Column(BigInteger, default=0)
    client_error_requests = Column(BigInteger, default=0)
    server_error_requests = Column(BigInteger, default=0)

    # 流量统计
    total_bytes_sent = Column(BigInteger, default=0)
    total_bytes_received = Column(BigInteger, default=0)

    # 性能统计
    avg_response_time = Column(Integer)
    min_response_time = Column(Integer)
    max_response_time = Column(Integer)
    p50_response_time = Column(Integer)
    p95_response_time = Column(Integer)
    p99_response_time = Column(Integer)

    # WAF 统计
    waf_blocked_requests = Column(BigInteger, default=0)
    waf_logged_requests = Column(BigInteger, default=0)

    # 限流统计
    rate_limited_requests = Column(BigInteger, default=0)

    # TLS 统计
    tls_requests = Column(BigInteger, default=0)
    non_tls_requests = Column(BigInteger, default=0)

    # 唯一访客统计
    unique_ips = Column(Integer, default=0)
    unique_user_agents = Column(Integer, default=0)

    # 元数据
    stats_metadata = Column(JSONB, default={})

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"CaddyStatsTbl(id={self.id}, period={self.stat_period}, dimension={self.dimension_type}, requests={self.total_requests})"

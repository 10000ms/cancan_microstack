"""
Caddy 限流配置表 ORM 模型
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


class CaddyRateLimitTbl(TableBase):
    """Caddy 限流配置表"""
    __tablename__ = 'caddy_rate_limit_tbl'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 限流规则基本信息
    rule_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    # 匹配条件
    match_type = Column(String(50), nullable=False)
    match_pattern = Column(String(500))
    match_domain = Column(String(255))

    # 限流配置
    limit_type = Column(String(50), nullable=False, default='request')
    limit_value = Column(Integer, nullable=False)
    limit_window = Column(Integer, nullable=False, default=60)
    limit_key = Column(String(50), default='ip')

    # 突发流量配置
    burst_size = Column(Integer, default=0)

    # 响应配置
    block_status_code = Column(Integer, default=429)
    block_message = Column(String(500), default='Too Many Requests')

    # 白名单/黑名单
    whitelist_ips = Column(ARRAY(Text))
    blacklist_ips = Column(ARRAY(Text))

    # 状态和优先级
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=100)

    # 元数据
    rule_metadata = Column(JSONB, default={})

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"CaddyRateLimitTbl(id={self.id}, rule_name={self.rule_name}, limit_value={self.limit_value}/{self.limit_window}s)"

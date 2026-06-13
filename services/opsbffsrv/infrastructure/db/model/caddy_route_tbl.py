"""
Caddy 路由配置表 ORM 模型
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    SmallInteger,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from linglong_web import TableBase


class CaddyRouteTbl(TableBase):
    """Caddy 路由配置表"""
    __tablename__ = 'caddy_route_tbl'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 路由基本信息
    route_name = Column(String(100), nullable=False, unique=True)
    domain = Column(String(255), nullable=False)
    path_pattern = Column(String(500), nullable=False)

    # 上游服务配置
    upstream_service = Column(String(100), nullable=False)
    upstream_host = Column(String(100), nullable=False)
    upstream_port = Column(Integer, nullable=False)

    # 路由选项
    strip_path_prefix = Column(String(200))
    add_path_prefix = Column(String(200))
    enable_https = Column(Boolean, default=True)
    force_https = Column(Boolean, default=True)

    # WAF 配置
    enable_waf = Column(Boolean, default=True)
    waf_rule_set = Column(String(50), default='default')

    # 负载均衡配置
    load_balance_strategy = Column(String(50), default='round_robin')
    health_check_path = Column(String(200))
    health_check_interval = Column(Integer, default=30)

    # 状态和元数据
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=100)
    route_metadata = Column(JSONB, default={})
    description = Column(Text)

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"CaddyRouteTbl(id={self.id}, route_name={self.route_name}, upstream_service={self.upstream_service})"

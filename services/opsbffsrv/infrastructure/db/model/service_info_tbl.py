"""
服务信息表 ORM 模型
"""
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    SmallInteger,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from linglong_web import TableBase

from cancan_microstack.public.const.caddy_consts import InternalRequestPath


class ServiceInfoTbl(TableBase):
    """服务信息表"""
    __tablename__ = 'service_info_tbl'

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 业务字段
    service_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    service_type = Column(String(50), default='business')
    health_check_path = Column(String(255), default=InternalRequestPath.HEALTH_CHECK.value)
    service_metadata = Column(JSONB, default=dict)
    expected_status = Column(String(20), default='running')
    desired_replicas = Column(SmallInteger, default=1)
    actual_replicas = Column(SmallInteger, default=0)
    last_scale_at = Column(TIMESTAMP(timezone=True))
    scale_policy = Column(JSONB, default=dict)
    registered_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    last_registered_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"ServiceInfoTbl(id={self.id}, service_name={self.service_name}, type={self.service_type})"

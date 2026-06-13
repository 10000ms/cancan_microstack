"""
服务行为日志表 ORM 模型
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    SmallInteger,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from linglong_web import TableBase


class ServiceActionLogTbl(TableBase):
    """服务行为日志表"""
    __tablename__ = 'service_action_log_tbl'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 业务字段
    service_name = Column(String(100), nullable=False)
    instance_id = Column(String(50))
    action_type = Column(String(50), nullable=False)
    action_status = Column(String(20), nullable=False)
    action_detail = Column(JSONB, default={})
    error_message = Column(Text)
    triggered_by = Column(String(50), default='system')
    action_metadata = Column(JSONB, default={})

    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"ServiceActionLogTbl(id={self.id}, service={self.service_name}, action={self.action_type}, status={self.action_status})"

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


class ServiceInfoTbl(TableBase):
    """
    服务信息表
    
    存储所有注册过的服务的基本信息和多实例配置。
    支持服务扩缩容管理和期望状态控制。
    """
    __tablename__ = 'service_info_tbl'
    
    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 业务字段
    service_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    service_type = Column(String(50), default='business')
    health_check_path = Column(String(255), default='/internal/health')
    service_metadata = Column(JSONB, default=dict)
    
    # 多实例支持字段
    expected_status = Column(String(20), default='running')      # 期望状态: running|stopped
    desired_replicas = Column(SmallInteger, default=1)            # 期望副本数
    actual_replicas = Column(SmallInteger, default=0)             # 实际运行副本数
    last_scale_at = Column(TIMESTAMP(timezone=True))              # 最后Scale操作时间
    scale_policy = Column(JSONB, default=dict)                    # Scale策略配置
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
        return (
            f"ServiceInfoTbl(id={self.id}, service_name={self.service_name}, "
            f"type={self.service_type}, expected_status={self.expected_status}, "
            f"desired_replicas={self.desired_replicas}, actual_replicas={self.actual_replicas})"
        )

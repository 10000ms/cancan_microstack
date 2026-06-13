"""
服务操作记录表 ORM 模型
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


class ServiceOperationTbl(TableBase):
    """
    服务操作记录表
    
    记录所有服务操作的完整生命周期，支持异步操作追踪。
    包括启动、停止、重启、扩缩容、重建等操作。
    """
    __tablename__ = 'service_operation_tbl'
    
    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 操作标识
    operation_id = Column(String, nullable=False, unique=True)  # 唯一操作ID (nanoid生成)
    
    # 操作信息
    operation_type = Column(String(20), nullable=False)  # start|stop|restart|scale
    service_name = Column(String(100), nullable=False)   # 服务名称 (如 besrv.service)
    
    # 操作参数
    operation_params = Column(JSONB, default={})  # 操作参数 (JSON格式)
    
    # 操作状态
    status = Column(String(20), nullable=False)  # pending|running|success|failed|timeout
    
    # 执行时间信息
    started_at = Column(TIMESTAMP(timezone=True))    # 开始执行时间
    completed_at = Column(TIMESTAMP(timezone=True))  # 完成时间
    
    # 结果信息
    result = Column(JSONB, default={})  # 执行结果详情 (JSON格式)
    error_message = Column(Text)        # 错误信息 (失败时记录)
    
    # 重试信息
    retry_count = Column(SmallInteger, default=0)     # 已重试次数
    max_retries = Column(SmallInteger, default=3)     # 最大重试次数
    last_retry_at = Column(TIMESTAMP(timezone=True))  # 最后一次重试时间
    
    # 审计信息
    initiated_by = Column(String(100))    # 操作发起者
    initiated_from = Column(String(100))  # 发起来源
    
    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    __table_args__ = (
        {'extend_existing': True},
    )
    
    def __repr__(self):
        return (
            f"ServiceOperationTbl(id={self.id}, operation_id={self.operation_id}, "
            f"type={self.operation_type}, service={self.service_name}, "
            f"status={self.status})"
        )

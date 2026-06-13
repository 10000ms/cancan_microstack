"""
执行审计日志表模型 / Execution Audit Log Table Model
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    SmallInteger,
    TIMESTAMP,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
)
from sqlalchemy.sql import func
from linglong_web import TableBase


class ExecutionLogTbl(TableBase):
    """
    执行审计日志表 execution log
    """
    __tablename__ = 'execution_log_tbl'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_instance_id = Column(UUID(as_uuid=True), ForeignKey('node_instance_tbl.id'), nullable=False)

    attempt_no = Column(Integer, nullable=False)  # 第几次尝试

    # 动作快照 (请求前)
    request_snapshot = Column(JSONB)

    # 结果快照 (响应后)
    response_snapshot = Column(JSONB)

    status = Column(String(20))  # SUCCESS, FAILURE, TIMEOUT (可以是字符串，比Enum灵活点)
    error_detail = Column(Text)

    start_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    end_time = Column(TIMESTAMP(timezone=True))
    duration_ms = Column(Integer)

    # 标准字段 (与 SQL schema 保持一致)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

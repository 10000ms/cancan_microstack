"""
工作流运行实例表模型 / Workflow Run Instance Table Model
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
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
from cancan_microstack.public.const.workflow_consts import WorkflowStatusEnum


class WorkflowRunTbl(TableBase):
    """
    工作流运行实例表 run instance
    """
    __tablename__ = 'workflow_run_tbl'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('workflow_definition_tbl.id'), nullable=False)

    status = Column(String(20), default=WorkflowStatusEnum.PENDING.value, index=True)

    # 触发源信息
    trigger_type = Column(String(20), nullable=False)
    trigger_context = Column(JSONB, default=dict)  # 触发时的元数据

    # 全局上下文数据 (随流程流动)
    global_context = Column(JSONB, default=dict)

    # 工作流定义快照字段，确保运行时使用固定版本
    # Workflow definition snapshot fields to guarantee immutable executions
    definition_version = Column(Integer)
    definition_snapshot = Column(JSONB)

    started_at = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    finished_at = Column(TIMESTAMP(timezone=True))
    duration_ms = Column(Integer)

    # 标准字段 (与 SQL schema 保持一致)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

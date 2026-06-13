"""
工作流版本快照表模型 / Workflow Definition Version Snapshot Table Model
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    Boolean,
    TIMESTAMP,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
)
from sqlalchemy.sql import func
from linglong_web import TableBase


class WorkflowDefinitionVersionTbl(TableBase):
    """工作流版本快照表 / Workflow definition history table"""

    __tablename__ = 'workflow_definition_version_tbl'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey('workflow_definition_tbl.id'), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    schedule = Column(String(100))
    graph_data = Column(JSONB, default=dict)
    nodes_config = Column(JSONB, nullable=False, default=dict)
    global_context = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=False)
    change_summary = Column(String(255))

    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

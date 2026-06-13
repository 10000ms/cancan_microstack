"""
工作流引擎告警表模型 / Workflow engine alert table model
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    SmallInteger,
    TIMESTAMP,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB,
)
from sqlalchemy.sql import func

from linglong_web import TableBase
from cancan_microstack.public.schemas.infra.enums import (
    WorkflowEngineAlertSeverity,
    WorkflowEngineAlertStatus,
)


class WorkflowEngineAlertTbl(TableBase):
    """
    Workflow engine alert records
    """

    __tablename__ = "workflow_engine_alert_tbl"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_run_tbl.id"), nullable=True)
    node_id = Column(String(64), nullable=False)
    loop_index = Column(Integer, nullable=False, default=1)
    severity = Column(String(16), nullable=False, default=WorkflowEngineAlertSeverity.CRITICAL.value)
    category = Column(String(32), nullable=False)
    reason = Column(String(255), nullable=False)
    detail = Column(JSONB, nullable=True)
    status = Column(String(16), nullable=False, default=WorkflowEngineAlertStatus.OPEN.value, index=True)
    acknowledged_by = Column(String(64))
    acknowledged_at = Column(TIMESTAMP(timezone=True))
    resolved_by = Column(String(64))
    resolved_at = Column(TIMESTAMP(timezone=True))
    note = Column(Text)

    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(
        TIMESTAMP(timezone=True),
        default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = ({"extend_existing": True},)

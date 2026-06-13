"""
工作流定义表模型 / Workflow Definition Table Model
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    SmallInteger,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
)
from sqlalchemy.sql import func
from linglong_web import TableBase


class WorkflowDefinitionTbl(TableBase):
    """
    工作流定义表 definition
    """
    __tablename__ = 'workflow_definition_tbl'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    schedule = Column(String(100))

    # 前端 Vue Flow 的 UI 数据 (节点坐标, 连线等)
    graph_data = Column(JSONB, default=dict)

    # 核心逻辑配置 (扁平化的节点 Map, key为节点ID)
    nodes_config = Column(JSONB, nullable=False, default=dict)

    # 编排级全局上下文（用于注入所有节点）
    # Global context defined at workflow level (injected into every node)
    global_context = Column(JSONB, default=dict)

    # 是否启用 (决定 Scanner 是否扫描)
    is_active = Column(Boolean, default=False)
    version = Column(Integer, nullable=False, default=1)
    change_summary = Column(String(255))

    # 标准字段 (与 SQL schema 保持一致)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

"""
节点运行实例表模型 / Node Run Instance Table Model
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
from cancan_microstack.public.const.workflow_consts import NodeStatusEnum


class NodeInstanceTbl(TableBase):
    """
    节点运行实例表 node instance
    """
    __tablename__ = 'node_instance_tbl'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey('workflow_run_tbl.id'), nullable=False)

    # 对应 JSON 图中的 key (如 "step_1")
    node_id = Column(String(50), nullable=False)

    # 循环轮次 (默认为 1)
    loop_index = Column(Integer, default=1, nullable=False)

    status = Column(String(20), default=NodeStatusEnum.PENDING.value, index=True)

    # 数据流转
    input_data = Column(JSONB, default=dict)  # 进入该节点时的入参
    final_output = Column(JSONB, default=dict)  # 该节点产出的结果

    # 统计
    attempt_count = Column(Integer, default=0)
    error_msg = Column(Text)

    # 标准字段 (与 SQL schema 保持一致)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

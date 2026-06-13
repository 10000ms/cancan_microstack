"""Workflow task constants.

集中声明 Celery 任务名称，避免散落在多个模块中造成字符串不一致。
Centralizes Celery task identifiers to keep task names consistent across modules.
"""
from enum import StrEnum


# Immutable workflow node IDs
# 工作流内置节点 ID（不可变，前端/后端都应视为保留字）
IMMUTABLE_START_NODE_IDS: frozenset[str] = frozenset({
    "start",
    "start_node",
    "node-start",
    "node_start",
})

IMMUTABLE_END_NODE_IDS: frozenset[str] = frozenset({
    "end",
    "end_node",
    "node-end",
    "node_end",
})


class WorkflowTask(StrEnum):
    EXECUTE_NODE = "workflows.execute_node"
    SCAN_SCHEDULED = "workflows.scan_scheduled"


class WorkflowStatusEnum(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class NodeStatusEnum(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"
    SUSPENDED = "SUSPENDED"  # 等待回调
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"  # 跟随流程取消


class TriggerTypeEnum(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULE = "SCHEDULE"
    API = "API"


class WorkflowEngineAlertReason(StrEnum):
    """Workflow engine alert reasons to keep string identifiers consistent."""

    INVALID_RUN_ID = "INVALID_RUN_ID"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    WORKFLOW_DEFINITION_MISSING = "WORKFLOW_DEFINITION_MISSING"
    NODE_CONFIG_MISSING = "NODE_CONFIG_MISSING"
    NODE_EXECUTION_EXCEPTION = "NODE_EXECUTION_EXCEPTION"
    NODE_TERMINATED_WITHOUT_DOWNSTREAM = "NODE_TERMINATED_WITHOUT_DOWNSTREAM"

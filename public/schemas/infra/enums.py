from enum import (
    StrEnum,
    IntEnum,
)


class ServiceType(StrEnum):
    """服务类型"""
    INFRASTRUCTURE = "infrastructure"
    BUSINESS = "business"
    OPS = "ops"


class HookExecutionResult(StrEnum):
    """钩子执行结果"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TERMINATE = "TERMINATE"
    RETRY = "RETRY"


class HookPriority(IntEnum):
    """钩子优先级"""
    HIGHEST = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    LOWEST = 5


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class NodeStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"
    SUSPENDED = "SUSPENDED"  # 等待回调
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"  # 跟随流程取消


class TriggerType(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULE = "SCHEDULE"
    API = "API"


class NodeType(StrEnum):
    START = "START"
    ACTION = "ACTION"
    TRANSFORM = "TRANSFORM"
    LOGIC = "LOGIC"
    FORK = "FORK"  # 并行分支节点 / Parallel fork node
    JOIN = "JOIN"
    LOOP = "LOOP"
    END = "END"


class ConditionTruth(StrEnum):
    """条件求值标准化枚举 / Normalized enum for condition evaluations"""

    TRUE = "true"
    FALSE = "false"


class JoinMode(StrEnum):
    ALL = "ALL"
    ANY = "ANY"

class EndStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

class TransformEngine(StrEnum):
    """数据转换引擎枚举 / Enumerates transform engines"""

    JINJA2 = "JINJA2"
    JMESPATH = "JMESPATH"


class ExecutionLogStatus(StrEnum):
    """执行日志状态 / Execution log status"""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"


class TriggerDispatchStatus(StrEnum):
    """工作流触发指令状态 / Workflow trigger dispatch status"""

    DISPATCHED = "DISPATCHED"
    QUEUED_NO_ENTRY = "QUEUED_NO_ENTRY"


class CallbackAckStatus(StrEnum):
    """回调确认结果 / Callback acknowledgement status"""

    ACCEPTED = "ACCEPTED"
    IGNORED = "IGNORED"


class WorkflowEngineAlertStatus(StrEnum):
    """工作流引擎告警状态枚举 / Workflow engine alert lifecycle status"""

    OPEN = "OPEN"
    ACKED = "ACKED"
    RESOLVED = "RESOLVED"


class WorkflowEngineAlertSeverity(StrEnum):
    """工作流引擎告警严重程度 / Workflow engine alert severity"""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class WorkflowEngineAlertCategory(StrEnum):
    """告警分类，便于前端筛选 / Alert category for filtering"""

    ORCHESTRATOR_GUARD = "ORCHESTRATOR_GUARD"
    TRANSPORT_PIPELINE = "TRANSPORT_PIPELINE"
    CALLBACK = "CALLBACK"
    DATA_INTEGRITY = "DATA_INTEGRITY"

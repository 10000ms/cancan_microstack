"""
Workflow-related Pydantic models shared by infra services.
工作流相关的 Pydantic 数据模型，供基础设施服务共享
"""
import uuid
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Union,
)

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from cancan_microstack.public.const.workflow_consts import WorkflowEngineAlertReason
from cancan_microstack.public.schemas.infra.enums import (
    CallbackAckStatus,
    EndStatus,
    ExecutionLogStatus,
    JoinMode,
    NodeStatus,
    NodeType,
    TransformEngine,
    TriggerDispatchStatus,
    TriggerType,
    WorkflowStatus,
    WorkflowEngineAlertStatus,
    WorkflowEngineAlertSeverity,
    WorkflowEngineAlertCategory,
)


# ==================== VueFlow Graph Metadata ====================
class VueFlowPosition(BaseModel):
    """VueFlow 节点坐标 / VueFlow node coordinates"""

    model_config = ConfigDict(extra="allow")

    x: float
    y: float


class WorkflowGraphNode(BaseModel):
    """保存 VueFlow 节点的可视化信息 / Stores VueFlow node metadata"""

    model_config = ConfigDict(extra="allow")

    node_id: str
    label: str
    type: NodeType
    position: VueFlowPosition
    ui: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowGraphEdge(BaseModel):
    """保存 VueFlow 边的可视化信息 / Stores VueFlow edge metadata"""

    model_config = ConfigDict(extra="allow")

    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None
    animated: bool = False
    type: str = "smoothstep"


class WorkflowGraphData(BaseModel):
    """绘图数据载体，包含节点与连线 / Aggregated graph payload"""

    nodes: List[WorkflowGraphNode] = Field(default_factory=list)
    edges: List[WorkflowGraphEdge] = Field(default_factory=list)
    version: Optional[int] = None


# ==================== Node Configurations ====================
class TriggerRule(BaseModel):
    field: str
    operator: str
    value: Any


class TriggerGroup(BaseModel):
    logic: str = "AND"
    children: List[Union["TriggerGroup", TriggerRule]] = Field(default_factory=list)


class StartNodeConfig(BaseModel):
    trigger_rules: Optional[TriggerGroup] = None


class RequestConfig(BaseModel):
    method: str = "GET"
    url: str
    params: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    body_type: Literal["auto", "json", "form-urlencoded", "multipart", "raw"] = "auto"
    body: Any = None
    json_body: Any = None
    form_body: Any = None
    raw_body: Any = None
    timeout_seconds: int = 30


class RetryPolicy(BaseModel):
    enabled: bool = False
    max_attempts: int = 1
    interval_seconds: int = 5
    retry_on_status: Optional[List[Union[int, str]]] = None


class FailureStrategy(BaseModel):
    async_wait_timeout: int = 3600
    action: str = "FAIL_FLOW"


class ActionNodeConfig(BaseModel):
    async_mode: bool = False
    request: RequestConfig
    retry_policy: Optional[RetryPolicy] = None
    failure_strategy: Optional[FailureStrategy] = None
    context_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="响应字段映射到 global_context 业务键，格式: {'biz.user_id': 'json_body.data.user_id'}",
    )


class TransformNodeConfig(BaseModel):
    engine: TransformEngine = TransformEngine.JINJA2
    output_schema: Dict[str, str] = Field(default_factory=dict)


class LogicNodeConfig(BaseModel):
    condition: str
    true_next_node_id: Optional[str] = None
    false_next_node_id: Optional[str] = None


class ForkNodeConfig(BaseModel):
    branch_node_ids: List[str] = Field(default_factory=list)
    branch_labels: Dict[str, str] = Field(default_factory=dict)


class JoinNodeConfig(BaseModel):
    mode: JoinMode = JoinMode.ALL
    timeout_seconds: int = 3600
    merge_strategy: str = "MAP"


class LoopNodeConfig(BaseModel):
    """循环节点配置，描述循环体入口与退出路径
    Loop node configuration describing loop body entry and exit paths"""

    condition: str
    body_entry_id: Optional[str] = Field(default=None, description="循环体入口节点 ID / Loop body entry node id")
    exit_node_id: Optional[str] = Field(default=None, description="循环退出节点 ID / Loop exit node id")
    jump_target_id: Optional[str] = Field(default=None,
                                          description="兼容字段，等价于 body_entry_id / Backward compatible alias of body_entry_id")
    max_iterations: int = 10

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        """保持兼容性：自动同步 body_entry 与旧字段 jump_target
        Keep backward compatibility by syncing body_entry with legacy jump_target"""

        # 如果历史数据只有 jump_target_id，则复制到 body_entry_id / migrate legacy payloads
        if self.body_entry_id is None and self.jump_target_id:
            self.body_entry_id = self.jump_target_id
        # 保持旧字段依旧可用 / keep legacy field populated for downstream consumers
        if self.body_entry_id and not self.jump_target_id:
            self.jump_target_id = self.body_entry_id


class EndNodeConfig(BaseModel):
    status: EndStatus = EndStatus.SUCCESS
    output_schema: Dict[str, str] = Field(default_factory=dict)


NodeConfigData = Union[
    StartNodeConfig,
    ActionNodeConfig,
    TransformNodeConfig,
    LogicNodeConfig,
    ForkNodeConfig,
    JoinNodeConfig,
    LoopNodeConfig,
    EndNodeConfig,
    Dict[str, Any],
]


class NodeConfig(BaseModel):
    """节点逻辑配置 / Logical node definition"""

    id: str
    name: str
    type: NodeType
    next_node_id: Optional[str] = None
    next_node_ids: List[str] = Field(default_factory=list)
    config: Optional[NodeConfigData] = None


# ==================== Workflow Definition ====================
class WorkflowDefinitionBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    schedule: Optional[str] = Field(default=None, max_length=100)
    graph_data: WorkflowGraphData = Field(default_factory=WorkflowGraphData)
    nodes_config: Dict[str, NodeConfig] = Field(default_factory=dict)
    global_context: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False


class WorkflowDefinitionCreate(WorkflowDefinitionBase):
    pass


class WorkflowDefinitionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    schedule: Optional[str] = Field(default=None, max_length=100)
    graph_data: Optional[WorkflowGraphData] = None
    nodes_config: Optional[Dict[str, NodeConfig]] = None
    global_context: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    flag: Optional[int] = None
    change_summary: Optional[str] = Field(default=None, max_length=255)


class WorkflowDefinition(WorkflowDefinitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int = 1
    flag: int
    created_time: datetime
    update_time: datetime


class WorkflowDefinitionVersion(BaseModel):
    """工作流版本快照 / Workflow definition version snapshot"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    version: int
    name: str
    description: Optional[str] = None
    schedule: Optional[str] = None
    graph_data: WorkflowGraphData = Field(default_factory=WorkflowGraphData)
    nodes_config: Dict[str, NodeConfig] = Field(default_factory=dict)
    global_context: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = False
    change_summary: Optional[str] = None
    created_time: datetime


class WorkflowVersionListResponse(BaseModel):
    """工作流版本列表响应 / Workflow version listing response"""

    workflow_id: uuid.UUID
    versions: List[WorkflowDefinitionVersion] = Field(default_factory=list)


class WorkflowListQuery(BaseModel):
    keyword: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class WorkflowListResponse(BaseModel):
    list: List[WorkflowDefinition]
    total: int
    page: int
    page_size: int


class DuplicateWorkflowPayload(BaseModel):
    source_workflow_id: str
    name: str


# ==================== Workflow Run & Instances ====================
class WorkflowRunQuery(BaseModel):
    workflow_id: Optional[str] = None
    reqid: Optional[str] = None
    status: Optional[WorkflowStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class WorkflowRunBase(BaseModel):
    workflow_id: uuid.UUID
    status: WorkflowStatus = WorkflowStatus.PENDING
    trigger_type: TriggerType
    trigger_context: Dict[str, Any] = Field(default_factory=dict)
    global_context: Dict[str, Any] = Field(default_factory=dict)
    definition_version: Optional[int] = None
    definition_snapshot: Optional[Dict[str, Any]] = None


class WorkflowRunCreate(WorkflowRunBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)


class WorkflowRunUpdate(BaseModel):
    status: Optional[WorkflowStatus] = None
    global_context: Optional[Dict[str, Any]] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class WorkflowRun(WorkflowRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_name: Optional[str] = None
    reqid: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    flag: int
    created_time: datetime
    update_time: datetime

    @model_validator(mode="after")
    def _hydrate_reqid(self):
        """从运行上下文补全 reqid 字段。
        Hydrate reqid from run contexts when response payload lacks reqid.
        """

        if self.reqid:
            return self

        for context_data in (self.trigger_context, self.global_context):
            if not isinstance(context_data, dict):
                continue
            candidate = str(context_data.get("reqid") or "").strip()
            if candidate:
                self.reqid = candidate
                break

        return self


class WorkflowRunListResponse(BaseModel):
    list: List[WorkflowRun]
    total: int
    page: int
    page_size: int


class NodeInstanceBase(BaseModel):
    run_id: uuid.UUID
    node_id: str
    loop_index: int = 1
    status: NodeStatus = NodeStatus.PENDING
    input_data: Dict[str, Any] = Field(default_factory=dict)
    final_output: Optional[Dict[str, Any]] = None
    attempt_count: int = 0
    error_msg: Optional[str] = None


class NodeInstance(NodeInstanceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    flag: int
    created_time: datetime
    update_time: datetime


class ExecutionLogBase(BaseModel):
    node_instance_id: uuid.UUID
    attempt_no: int
    status: ExecutionLogStatus = ExecutionLogStatus.PENDING
    request_snapshot: Dict[str, Any] = Field(default_factory=dict)
    response_snapshot: Optional[Dict[str, Any]] = None
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("started_at", "start_time"),
        serialization_alias="started_at",
    )
    finished_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("finished_at", "end_time"),
        serialization_alias="finished_at",
    )


class ExecutionLog(ExecutionLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    flag: int
    created_time: datetime
    update_time: datetime


class NodeExecutionHistory(BaseModel):
    node_id: str
    loop_index: int
    status: NodeStatus
    output: Optional[Dict[str, Any]] = None
    logs: List[ExecutionLog] = Field(default_factory=list)


class NodeExecutionHistoryResponse(BaseModel):
    histories: List[NodeExecutionHistory] = Field(default_factory=list)


# ==================== Runtime Context Models ====================
class NodeOutput(BaseModel):
    output: Optional[Dict[str, Any]] = None
    status: NodeStatus = NodeStatus.PENDING


class WorkflowExecutionContext(BaseModel):
    run_id: uuid.UUID
    global_context: Dict[str, Any] = Field(default_factory=dict)
    nodes: Dict[str, NodeOutput] = Field(default_factory=dict)
    loop_index: int = 1
    callback_url: Optional[str] = None


class HttpResponseOutput(BaseModel):
    status_code: int
    headers: Dict[str, Any]
    text: Optional[str] = None
    json_body: Optional[Dict[str, Any]] = None
    ok: bool = True


# ==================== Public API Payloads ====================
class WorkflowTriggerRequest(BaseModel):
    trigger_context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowTriggerResponse(BaseModel):
    run_id: str
    dispatch_status: TriggerDispatchStatus


class WorkflowRollbackRequest(BaseModel):
    """工作流回滚请求载体 / Workflow rollback request payload"""

    target_version: int = Field(..., ge=1)
    reason: Optional[str] = Field(default=None, max_length=255)


class WorkflowStats(BaseModel):
    total_definitions: int = 0
    active_definitions: int = 0
    scheduled_definitions: int = 0
    total_runs: int = 0
    runs_by_status: Dict[str, int] = Field(default_factory=dict)
    runs_today: int = 0
    failed_runs_today: int = 0
    success_rate_24h: float = 0.0
    running_runs: int = 0
    pending_runs: int = 0
    active_node_instances: int = 0
    waiting_node_instances: int = 0
    inflight_attempts: int = 0
    next_cron_window: Optional[str] = None


class RunGraphNode(BaseModel):
    node_id: str
    label: str
    type: NodeType
    status: NodeStatus
    loop_index: int = 1
    position: Optional[VueFlowPosition] = None
    ui: Dict[str, Any] = Field(default_factory=dict)
    last_output: Optional[Dict[str, Any]] = None
    node_config_snapshot: Optional[Dict[str, Any]] = None


class RunGraphResponse(BaseModel):
    run_id: str
    status: WorkflowStatus
    graph_version: Optional[int] = None
    nodes: List[RunGraphNode] = Field(default_factory=list)
    edges: List[WorkflowGraphEdge] = Field(default_factory=list)


class CallbackAckResponse(BaseModel):
    status: CallbackAckStatus


# ==================== Engine Alerts ====================
class WorkflowEngineAlertDetail(BaseModel):
    """工作流引擎告警详情载荷 / Structured alert detail payload."""

    model_config = ConfigDict(extra="allow")

    run_id: Optional[str] = None
    workflow_id: Optional[str] = None
    node_id: Optional[str] = None
    error: Optional[str] = None


class WorkflowEngineAlertBase(BaseModel):
    run_id: Optional[uuid.UUID] = None
    node_id: str
    loop_index: int = 1
    severity: WorkflowEngineAlertSeverity = WorkflowEngineAlertSeverity.CRITICAL
    category: WorkflowEngineAlertCategory = WorkflowEngineAlertCategory.ORCHESTRATOR_GUARD
    reason: WorkflowEngineAlertReason
    detail: WorkflowEngineAlertDetail = Field(default_factory=WorkflowEngineAlertDetail)
    status: WorkflowEngineAlertStatus = WorkflowEngineAlertStatus.OPEN
    note: Optional[str] = None


class WorkflowEngineAlert(WorkflowEngineAlertBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_time: datetime
    update_time: datetime


class WorkflowEngineAlertCreate(WorkflowEngineAlertBase):
    pass


class WorkflowEngineAlertAckRequest(BaseModel):
    operator: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)


class WorkflowEngineAlertQuery(BaseModel):
    status: Optional[WorkflowEngineAlertStatus] = None
    severity: Optional[WorkflowEngineAlertSeverity] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    run_id: Optional[str] = None


class WorkflowEngineAlertListResponse(BaseModel):
    list: List[WorkflowEngineAlert] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

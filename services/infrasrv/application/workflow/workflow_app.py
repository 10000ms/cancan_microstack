"""
工作流应用服务
Workflow Application Service

作为应用层，它负责编排领域服务和基础设施服务，以完成完整的工作流功能。
As the application layer, it orchestrates domain and infrastructure services to deliver complete workflow functionality.
"""
import uuid
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from cancan_microstack.public.error import (
    HTTPException,
    ParamError,
)
from cancan_microstack.public.const.workflow_consts import WorkflowEngineAlertReason
from cancan_microstack.public.schemas.infra import workflow as wt
from cancan_microstack.public.schemas.infra.enums import (
    CallbackAckStatus,
    ExecutionLogStatus,
    NodeType,
    WorkflowEngineAlertSeverity,
    WorkflowEngineAlertCategory,
)
from linglong_web import LinglongConfig
from linglong_web.utils import (
    get_request_id,
    set_request_id,
)
from cancan_microstack.services.infrasrv.application.workflow.workflow_queue import (
    enqueue_node_execution,
    register_inline_orchestrator,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate import workflow_op
from cancan_microstack.services.infrasrv.domain.workflow.engine import workflow_engine
from cancan_microstack.services.infrasrv.domain.workflow.workflow_domain import workflow_domain
from linglong_web.utils import logger


class WorkflowApp:
    """编排工作流相关用例 / Orchestrates workflow-related use cases."""

    @staticmethod
    def _serialize_output_payload(output: Any) -> Optional[Dict[str, Any]]:
        """将领域输出转换为可存储的 JSON 字典 / Convert node output into a JSON-serializable dict."""

        if output is None:
            return None
        if hasattr(output, "model_dump"):
            dumped = output.model_dump()
            return dumped if isinstance(dumped, dict) else {"data": dumped}
        if isinstance(output, dict):
            return output
        if isinstance(output, list):
            return {"items": output}
        return {"value": output}

    @staticmethod
    def _merge_runtime_context(
            current_context: Optional[Dict[str, Any]],
            node_id: str,
            node_status: wt.NodeStatus,
            output: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """将节点执行结果写入全局上下文运行时命名空间。
        Merge node execution result into global context runtime namespace.
        """

        merged_context = dict(current_context or {})
        runtime_payload = dict(merged_context.get("__runtime__") or {})
        node_outputs = dict(runtime_payload.get("node_outputs") or {})

        node_outputs[node_id] = {
            "status": node_status.value,
            "output": output,
        }

        runtime_payload["node_outputs"] = node_outputs
        runtime_payload["last_node_id"] = node_id
        runtime_payload["last_output"] = output
        runtime_payload["last_status"] = node_status.value
        merged_context["__runtime__"] = runtime_payload

        return merged_context

    @staticmethod
    def _extract_value_by_path(payload: Optional[Dict[str, Any]], path: str) -> tuple[Any, bool]:
        """按点路径提取值 / Extract value by dot path."""

        if not isinstance(payload, dict) or not path:
            return None, False

        current: Any = payload
        for segment in path.split("."):
            seg = segment.strip()
            if not seg:
                return None, False

            if isinstance(current, dict):
                if seg not in current:
                    return None, False
                current = current.get(seg)
                continue

            if isinstance(current, list):
                if not seg.isdigit():
                    return None, False
                index = int(seg)
                if index < 0 or index >= len(current):
                    return None, False
                current = current[index]
                continue

            return None, False

        return current, True

    @staticmethod
    def _set_nested_value(target: Dict[str, Any], path: str, value: Any) -> None:
        """按点路径写入值 / Set value by dot path."""

        segments = [seg.strip() for seg in path.split(".") if seg.strip()]
        if not segments:
            return

        cursor = target
        for segment in segments[:-1]:
            next_value = cursor.get(segment)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[segment] = next_value
            cursor = next_value

        cursor[segments[-1]] = value

    @classmethod
    def _apply_action_context_mappings(
            cls,
            current_context: Optional[Dict[str, Any]],
            node_config: wt.NodeConfig,
            output: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """将 Action 节点输出映射到 global_context 业务键。"""

        merged_context = dict(current_context or {})
        if node_config.type != NodeType.ACTION:
            return merged_context

        config = node_config.config
        mappings = getattr(config, "context_mappings", None) if config else None
        if not isinstance(mappings, dict) or not mappings:
            return merged_context

        for target_key, source_path in mappings.items():
            if not isinstance(target_key, str) or not target_key.strip():
                continue
            if target_key.startswith("__runtime__"):
                logger.warning("Skip mapping to reserved key '__runtime__': %s", target_key)
                continue
            if not isinstance(source_path, str) or not source_path.strip():
                continue

            value, found = cls._extract_value_by_path(output, source_path.strip())
            if not found:
                logger.warning(
                    "Action context mapping source path not found: node=%s target=%s source=%s",
                    node_config.id,
                    target_key,
                    source_path,
                )
                continue

            cls._set_nested_value(merged_context, target_key.strip(), value)

        return merged_context

    @staticmethod
    def _requires_async_callback(node_config: wt.NodeConfig) -> bool:
        """判断节点是否需要异步回调 / Return True when the node expects async callbacks."""

        if node_config.type != NodeType.ACTION:
            return False
        config = node_config.config
        return bool(config and getattr(config, "async_mode", False))

    @staticmethod
    def _build_callback_url(node_instance_id: uuid.UUID) -> str:
        """根据节点实例构造回调地址 / Build callback URL for async workers."""

        base = LinglongConfig.INFRASRV_HOST.rstrip("/") if LinglongConfig.INFRASRV_HOST else ""
        return f"{base}/v1/infrasrv/callbacks/{node_instance_id}" if base else f"/v1/infrasrv/callbacks/{node_instance_id}"

    @staticmethod
    def _build_definition_snapshot(definition: wt.WorkflowDefinition) -> Dict[str, Any]:
        """生成运行使用的工作流定义快照 / Build immutable workflow definition snapshot for runs."""

        return definition.model_dump(mode="json")

    @staticmethod
    def _normalize_trigger_context(trigger_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """确保触发上下文带有 reqid，并复用 Linglong 协程上下文能力。
        Ensure trigger context always includes reqid and reuses Linglong coroutine context.
        """

        normalized = dict(trigger_context or {})
        provided_reqid = str(normalized.get("reqid") or "").strip()

        if provided_reqid:
            set_request_id(provided_reqid)
            reqid = provided_reqid
        else:
            reqid = str(get_request_id() or "").strip()
            if not reqid:
                set_request_id(None)
                reqid = str(get_request_id() or "").strip()

        normalized["reqid"] = reqid
        return normalized

    @staticmethod
    def _extract_reqid_from_run(run: wt.WorkflowRun) -> str:
        """从运行上下文提取 reqid。
        Extract reqid from run contexts.
        """

        for context_data in (run.trigger_context, run.global_context):
            if not isinstance(context_data, dict):
                continue
            candidate = str(context_data.get("reqid") or "").strip()
            if candidate:
                return candidate
        return ""

    @staticmethod
    def _build_graph_adjacency(workflow_def: wt.WorkflowDefinition) -> Dict[str, List[str]]:
        """构建工作流邻接表，优先使用 graph_data.edges。
        Build workflow adjacency map, preferring graph_data.edges.
        """

        adjacency: Dict[str, List[str]] = {}
        graph_data = workflow_def.graph_data

        if graph_data and graph_data.edges:
            for edge in graph_data.edges:
                source = edge.source
                target = edge.target
                if not source or not target:
                    continue
                adjacency.setdefault(source, [])
                if target not in adjacency[source]:
                    adjacency[source].append(target)
            return adjacency

        for node_id, raw_node in workflow_def.nodes_config.items():
            node = wt.NodeConfig.model_validate(raw_node)
            adjacency[node_id] = list(node.next_node_ids or [])
        return adjacency

    @classmethod
    def _is_node_in_loop_body_subgraph(
            cls,
            workflow_def: wt.WorkflowDefinition,
            loop_node_id: str,
            loop_node: wt.NodeConfig,
            current_node_id: str,
    ) -> bool:
        """判断节点是否位于 LOOP 循环体子图。
        Determine whether a node belongs to LOOP body subgraph.
        """

        loop_config = loop_node.config
        if not isinstance(loop_config, wt.LoopNodeConfig):
            return False

        body_entry_id = loop_config.body_entry_id or loop_config.jump_target_id
        if not body_entry_id:
            return False

        if current_node_id == body_entry_id:
            return True

        boundary_nodes = set(loop_node.next_node_ids or [])
        if loop_config.exit_node_id:
            boundary_nodes.add(loop_config.exit_node_id)
        boundary_nodes.add(loop_node_id)

        adjacency = cls._build_graph_adjacency(workflow_def)
        visited = set()
        stack = [body_entry_id]

        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)

            if node_id == current_node_id:
                return True

            for next_id in adjacency.get(node_id, []):
                if next_id in boundary_nodes:
                    continue
                if next_id not in visited:
                    stack.append(next_id)

        return False

    @classmethod
    def _resolve_loop_reentry_controller(
            cls,
            workflow_def: wt.WorkflowDefinition,
            current_node_id: str,
    ) -> Optional[str]:
        """为循环体内无下游节点查找应回派的 LOOP 控制节点。
        Resolve LOOP controller for body-node dead-end re-dispatch.
        """

        for candidate_node_id, candidate_raw_config in workflow_def.nodes_config.items():
            candidate_node = wt.NodeConfig.model_validate(candidate_raw_config)
            if candidate_node.type != wt.NodeType.LOOP:
                continue
            if cls._is_node_in_loop_body_subgraph(
                    workflow_def=workflow_def,
                    loop_node_id=candidate_node_id,
                    loop_node=candidate_node,
                    current_node_id=current_node_id,
            ):
                return candidate_node_id
        return None

    async def _resolve_run_definition(self, run: wt.WorkflowRun) -> Optional[wt.WorkflowDefinition]:
        """优先使用运行绑定的快照，还原对应的工作流定义
        Prefer the definition snapshot bound to the run before hitting live storage."""

        if run.definition_snapshot:
            try:
                return wt.WorkflowDefinition.model_validate(run.definition_snapshot)
            except Exception as exc:  # noqa: BLE001 - fallback to DB fetch when snapshot corrupt
                logger.error(
                    "Failed to hydrate workflow definition snapshot for run %s: %s",
                    run.id,
                    exc,
                    exc_info=True,
                )
        return await workflow_op.get_workflow_definition_by_id(run.workflow_id)

    async def _emit_engine_alert(
            self,
            *,
            run_id: Optional[uuid.UUID],
            node_id: str,
            loop_index: int,
            reason: WorkflowEngineAlertReason,
            detail: wt.WorkflowEngineAlertDetail,
            severity: WorkflowEngineAlertSeverity = WorkflowEngineAlertSeverity.CRITICAL,
            category: WorkflowEngineAlertCategory = WorkflowEngineAlertCategory.ORCHESTRATOR_GUARD,
    ) -> None:
        """持久化工作流引擎告警，确保运维可见 / Persist workflow engine alert for operator visibility."""

        payload = wt.WorkflowEngineAlertCreate(
            run_id=run_id,
            node_id=node_id,
            loop_index=max(loop_index, 1),
            reason=reason,
            detail=detail,
            severity=severity,
            category=category,
        )
        try:
            await workflow_op.create_engine_alert(payload)
        except Exception as exc:  # noqa: BLE001 - best effort alert persistence
            logger.error("Failed to persist workflow engine alert: %s", exc, exc_info=True)

    async def _execute_node_orchestrator(self, run_id_str: str, node_id: str, loop_index: int):
        """协调单个节点执行（加载上下文 -> 执行 -> 落库 -> 派发下一节点）。"""

        try:
            run_id = uuid.UUID(run_id_str)
        except ValueError:
            logger.error(f"Invalid run ID format: {run_id_str}")
            await self._emit_engine_alert(
                run_id=None,
                node_id=node_id,
                loop_index=loop_index,
                reason=WorkflowEngineAlertReason.INVALID_RUN_ID,
                detail=wt.WorkflowEngineAlertDetail(run_id=run_id_str),
            )
            return

        # 1. 基础数据加载 / Load run + definition metadata
        run = await workflow_op.get_workflow_run_by_id(run_id)
        if not run:
            await self._emit_engine_alert(
                run_id=run_id,
                node_id=node_id,
                loop_index=loop_index,
                reason=WorkflowEngineAlertReason.RUN_NOT_FOUND,
                detail=wt.WorkflowEngineAlertDetail(run_id=run_id_str),
            )
            return

        run_reqid = self._extract_reqid_from_run(run)
        set_request_id(run_reqid or None)

        if run.status in [wt.WorkflowStatus.FAILURE, wt.WorkflowStatus.CANCELLED]:
            return

        workflow_def = await self._resolve_run_definition(run)
        if not workflow_def:
            await self._emit_engine_alert(
                run_id=run_id,
                node_id=node_id,
                loop_index=loop_index,
                reason=WorkflowEngineAlertReason.WORKFLOW_DEFINITION_MISSING,
                detail=wt.WorkflowEngineAlertDetail(workflow_id=str(run.workflow_id)),
            )
            await workflow_op.update_workflow_run_status(run_id, wt.WorkflowStatus.FAILURE)
            return
        raw_node_config = workflow_def.nodes_config.get(node_id)
        if not raw_node_config:
            logger.error(f"Node {node_id} not found in definition {workflow_def.id}")
            await self._emit_engine_alert(
                run_id=run_id,
                node_id=node_id,
                loop_index=loop_index,
                reason=WorkflowEngineAlertReason.NODE_CONFIG_MISSING,
                detail=wt.WorkflowEngineAlertDetail(
                    workflow_id=str(workflow_def.id),
                    node_id=node_id,
                ),
            )
            await workflow_op.update_workflow_run_status(run_id, wt.WorkflowStatus.FAILURE)
            return
        node_config = wt.NodeConfig.model_validate(raw_node_config)

        # 2. 准备节点实例与执行上下文 / Prepare node instance + execution context snapshot
        all_instances = await workflow_op.get_node_instances_by_run_id(run_id)
        instance = await workflow_op.upsert_node_instance(
            run_id=run_id,
            node_id=node_id,
            loop_index=loop_index,
        )
        nodes_map = {
            inst.node_id: wt.NodeOutput(output=inst.final_output, status=inst.status)
            for inst in all_instances
        }
        nodes_map[instance.node_id] = wt.NodeOutput(output=instance.final_output, status=instance.status)

        callback_url = None
        if self._requires_async_callback(node_config):
            callback_url = self._build_callback_url(instance.id)

        context = wt.WorkflowExecutionContext(
            run_id=run_id,
            global_context=run.global_context,
            nodes=nodes_map,
            loop_index=loop_index,
            callback_url=callback_url,
        )

        # 3. 创建执行日志骨架 / Create execution log skeleton
        log_entry = await workflow_op.create_execution_log(
            node_instance_id=instance.id,
            attempt_no=instance.attempt_count,
            request_snapshot=run.global_context,
        )

        try:
            # 4. 调用领域引擎执行节点 / Run node handler via workflow_engine
            output, status, next_node_ids, new_loop_index = await workflow_engine.process_node(
                workflow_def,
                node_config,
                context,
            )
            serialized_output = self._serialize_output_payload(output)

            # 5. 持久化节点结果 / Persist node + log result (if not pending)
            if status != wt.NodeStatus.PENDING:
                await workflow_op.update_node_instance_result(
                    instance_id=instance.id,
                    status=status,
                    final_output=serialized_output,
                )

                updated_context = self._merge_runtime_context(
                    current_context=run.global_context,
                    node_id=node_id,
                    node_status=status,
                    output=serialized_output,
                )
                updated_context = self._apply_action_context_mappings(
                    current_context=updated_context,
                    node_config=node_config,
                    output=serialized_output,
                )
                updated_run = await workflow_op.update_workflow_run_global_context(
                    run_id=run_id,
                    global_context=updated_context,
                )
                if updated_run:
                    run = updated_run

                await workflow_op.update_execution_log_result(
                    log_id=log_entry.id,
                    status=ExecutionLogStatus.SUCCESS,
                    response_snapshot=serialized_output,
                )

                if status == wt.NodeStatus.FAILURE:
                    await workflow_op.update_workflow_run_status(run_id, wt.WorkflowStatus.FAILURE)

                # 6. 派发下一批节点 / Dispatch downstream nodes
                for next_id in next_node_ids:
                    enqueue_node_execution(run_id_str, next_id, new_loop_index)

                if node_config.type == NodeType.END and status == wt.NodeStatus.SUCCESS:
                    # 结束节点成功意味着流程整体完成
                    # Successful END node completion marks the entire run as SUCCESS
                    await workflow_op.update_workflow_run_status(run_id, wt.WorkflowStatus.SUCCESS)
                elif status == wt.NodeStatus.SUCCESS and not next_node_ids:
                    loop_reentry_node_id = self._resolve_loop_reentry_controller(
                        workflow_def=workflow_def,
                        current_node_id=node_id,
                    )

                    if loop_reentry_node_id:
                        loop_controller_raw = workflow_def.nodes_config.get(loop_reentry_node_id)
                        if loop_controller_raw:
                            loop_controller = wt.NodeConfig.model_validate(loop_controller_raw)
                        else:
                            loop_controller = None

                        loop_controller_config = loop_controller.config if loop_controller else None
                        if isinstance(loop_controller_config, wt.LoopNodeConfig) and loop_controller is not None:
                            if new_loop_index >= loop_controller_config.max_iterations:
                                exit_targets = []
                                if loop_controller_config.exit_node_id:
                                    exit_targets.append(loop_controller_config.exit_node_id)
                                elif loop_controller.next_node_ids:
                                    exit_targets.extend(loop_controller.next_node_ids)

                                if exit_targets:
                                    for exit_node_id in exit_targets:
                                        enqueue_node_execution(run_id_str, exit_node_id, new_loop_index)
                                    return

                        # LOOP 循环体末端节点允许省略显式回边，此处自动回派 LOOP 控制节点
                        # Loop body tail nodes can omit explicit back-edge; auto-dispatch loop control node
                        enqueue_node_execution(run_id_str, loop_reentry_node_id, new_loop_index + 1)
                        return

                    # 非 END 节点执行成功但无下游节点，视为编排断点并终止流程
                    # Successful non-END node without downstream nodes is treated as an orchestration dead-end
                    await self._emit_engine_alert(
                        run_id=run_id,
                        node_id=node_id,
                        loop_index=loop_index,
                        reason=WorkflowEngineAlertReason.NODE_TERMINATED_WITHOUT_DOWNSTREAM,
                        detail=wt.WorkflowEngineAlertDetail(
                            run_id=str(run_id),
                            workflow_id=str(workflow_def.id),
                            node_id=node_id,
                            error="Node completed successfully but no downstream nodes were dispatched",
                        ),
                        severity=WorkflowEngineAlertSeverity.MAJOR,
                        category=WorkflowEngineAlertCategory.ORCHESTRATOR_GUARD,
                    )
                    await workflow_op.update_workflow_run_status(run_id, wt.WorkflowStatus.FAILURE)

        except Exception as exc:
            logger.error(
                "Node execution failed for instance %s: %s",
                instance.id,
                exc,
                exc_info=True,
            )
            await self._emit_engine_alert(
                run_id=run_id,
                node_id=node_id,
                loop_index=loop_index,
                reason=WorkflowEngineAlertReason.NODE_EXECUTION_EXCEPTION,
                detail=wt.WorkflowEngineAlertDetail(
                    run_id=str(run_id),
                    node_id=node_id,
                    error=str(exc),
                ),
                severity=WorkflowEngineAlertSeverity.MAJOR,
                category=WorkflowEngineAlertCategory.TRANSPORT_PIPELINE,
            )
            error_payload = {"error": str(exc)}
            await workflow_op.update_node_instance_result(
                instance_id=instance.id,
                status=wt.NodeStatus.FAILURE,
                final_output=error_payload,
                error_msg=str(exc),
            )
            await workflow_op.update_execution_log_result(
                log_id=log_entry.id,
                status=ExecutionLogStatus.FAILURE,
                response_snapshot=error_payload,
                error_detail=str(exc),
            )
            await workflow_op.update_workflow_run_status(run_id, wt.WorkflowStatus.FAILURE)

    async def create_workflow_definition(self, data: wt.WorkflowDefinitionCreate) -> wt.WorkflowDefinition:
        """创建工作流定义 / Persist workflow definition metadata."""

        if not data.name or not data.name.strip():
            raise ParamError("Workflow name cannot be empty")
        return await workflow_op.create_workflow_definition(data)

    async def list_workflow_definitions(self, page: int = 1, page_size: int = 20) -> wt.WorkflowListResponse:
        """分页列出工作流定义 / List workflow definitions with pagination metadata."""

        limit = page_size
        offset = (page - 1) * page_size
        workflows, total = await workflow_op.list_workflow_definitions(limit, offset)
        return wt.WorkflowListResponse(
            list=workflows,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_workflow_definition(self, workflow_id_str: str) -> wt.WorkflowDefinition:
        """查询工作流定义详情 / Fetch workflow definition by ID."""

        try:
            workflow_uuid = uuid.UUID(workflow_id_str)
        except ValueError:
            raise ParamError(f"Invalid workflow ID format: {workflow_id_str}")

        workflow = await workflow_op.get_workflow_definition_by_id(workflow_uuid)
        if not workflow:
            raise HTTPException(status_code=404, msg="Workflow not found")
        return workflow

    async def get_scheduled_workflows(self) -> List[wt.WorkflowDefinition]:
        """获取所有启用的定时工作流 / Return active scheduled workflows."""

        return await workflow_op.get_scheduled_workflows()

    async def list_workflow_versions(self, workflow_id_str: str, limit: int = 50) -> wt.WorkflowVersionListResponse:
        """列出工作流版本历史
        List workflow definition versions with optional limit."""

        try:
            workflow_uuid = uuid.UUID(workflow_id_str)
        except ValueError:
            raise ParamError(f"Invalid workflow ID format: {workflow_id_str}")

        versions = await workflow_op.list_workflow_versions(workflow_uuid, limit=limit)
        return wt.WorkflowVersionListResponse(workflow_id=workflow_uuid, versions=versions)

    async def list_workflow_runs(self, query: wt.WorkflowRunQuery) -> wt.WorkflowRunListResponse:
        """查询运行实例 / List workflow runs with optional filtering and pagination."""

        workflow_id = None
        if query.workflow_id:
            try:
                workflow_id = uuid.UUID(query.workflow_id)
            except ValueError:
                raise ParamError(f"Invalid workflow ID format: {query.workflow_id}")

        runs, total = await workflow_op.list_workflow_runs(
            workflow_id=workflow_id,
            reqid=query.reqid,
            limit=query.page_size,
            offset=(query.page - 1) * query.page_size,
            status=query.status,
            date_from=query.date_from,
            date_to=query.date_to,
        )
        return wt.WorkflowRunListResponse(
            list=runs,
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def trigger_workflow(
            self,
            workflow_id_str: str,
            payload: wt.WorkflowTriggerRequest,
            trigger_type: wt.TriggerType = wt.TriggerType.API,
    ) -> wt.WorkflowTriggerResponse:
        """触发工作流执行 / Trigger a workflow run and enqueue start nodes."""

        workflow = await self.get_workflow_definition(workflow_id_str)
        definition_snapshot = self._build_definition_snapshot(workflow)
        normalized_trigger_context = self._normalize_trigger_context(payload.trigger_context)
        run = await workflow_op.create_workflow_run(
            wt.WorkflowRunCreate(
                workflow_id=workflow.id,
                trigger_type=trigger_type,
                trigger_context=normalized_trigger_context,
                global_context=dict(normalized_trigger_context),
                definition_version=workflow.version,
                definition_snapshot=definition_snapshot,
            )
        )

        dispatch_status = wt.TriggerDispatchStatus.QUEUED_NO_ENTRY
        start_node: Optional[wt.NodeConfig] = None

        for cfg in workflow.nodes_config.values():
            candidate = wt.NodeConfig.model_validate(cfg)
            if candidate.type == NodeType.START:
                start_node = candidate
                break

        if start_node:
            next_ids = start_node.next_node_ids or []
            if next_ids:
                # 标记运行已开始，便于前端展示实时状态
                # Mark run as RUNNING so UI reflects in-progress execution
                await workflow_op.update_workflow_run_status(run.id, wt.WorkflowStatus.RUNNING)
            for nid in next_ids:
                enqueue_node_execution(str(run.id), nid, 1)
            if next_ids:
                dispatch_status = wt.TriggerDispatchStatus.DISPATCHED

        return wt.WorkflowTriggerResponse(run_id=str(run.id), dispatch_status=dispatch_status)

    async def get_run_graph_status(self, run_id_str: str) -> wt.RunGraphResponse:
        """查询运行图谱状态 / Return DAG visualization payload for a workflow run."""

        try:
            run_id = uuid.UUID(run_id_str)
        except ValueError:
            raise ParamError(f"Invalid run ID format: {run_id_str}")

        run = await workflow_op.get_workflow_run_by_id(run_id)
        if not run:
            raise HTTPException(status_code=404, msg="Run not found")

        workflow_def = await self._resolve_run_definition(run)
        if not workflow_def:
            raise HTTPException(status_code=404, msg="Workflow definition snapshot missing")
        graph_data = workflow_def.graph_data or wt.WorkflowGraphData()
        instances = await workflow_op.get_node_instances_by_run_id(run_id)
        instance_map = {inst.node_id: inst for inst in instances}

        def _to_plain_dict(raw_config: Any) -> Optional[Dict[str, Any]]:
            if raw_config is None:
                return None
            if isinstance(raw_config, dict):
                return raw_config
            if isinstance(raw_config, wt.NodeConfig):
                return raw_config.model_dump(mode="json")
            return None

        graph_nodes: List[wt.RunGraphNode] = []
        for node in graph_data.nodes:
            inst = instance_map.get(node.node_id)
            node_config_snapshot = _to_plain_dict(workflow_def.nodes_config.get(node.node_id))
            graph_nodes.append(
                wt.RunGraphNode(
                    node_id=node.node_id,
                    label=node.label,
                    type=node.type,
                    status=inst.status if inst else wt.NodeStatus.PENDING,
                    loop_index=inst.loop_index if inst else 1,
                    position=node.position,
                    ui=node.ui,
                    last_output=inst.final_output if inst else None,
                    node_config_snapshot=node_config_snapshot,
                )
            )

        # Include orphan node instances (if they no longer exist in graph metadata)
        for node_id, inst in instance_map.items():
            if any(existing.node_id == node_id for existing in graph_nodes):
                continue
            node_config_snapshot = _to_plain_dict(workflow_def.nodes_config.get(node_id))
            graph_nodes.append(
                wt.RunGraphNode(
                    node_id=node_id,
                    label=node_id,
                    type=wt.NodeType.ACTION,
                    status=inst.status,
                    loop_index=inst.loop_index,
                    position=None,
                    ui={},
                    last_output=inst.final_output,
                    node_config_snapshot=node_config_snapshot,
                )
            )

        return wt.RunGraphResponse(
            run_id=str(run.id),
            status=run.status,
            graph_version=graph_data.version,
            nodes=graph_nodes,
            edges=graph_data.edges,
        )

    async def get_node_history(self, run_id_str: str, node_id: str) -> wt.NodeExecutionHistoryResponse:
        """查询单个节点的执行历史 / Fetch node execution history for a run."""

        try:
            run_id = uuid.UUID(run_id_str)
        except ValueError:
            raise ParamError(f"Invalid run ID format: {run_id_str}")

        instances = await workflow_op.get_node_instances_by_run_and_node_id(run_id, node_id)
        history: List[wt.NodeExecutionHistory] = []
        for inst in instances:
            logs = await workflow_op.get_execution_logs_by_node_instance_id(inst.id)
            history.append(
                wt.NodeExecutionHistory(
                    node_id=inst.node_id,
                    loop_index=inst.loop_index,
                    status=inst.status,
                    output=inst.final_output,
                    logs=logs,
                )
            )
        return wt.NodeExecutionHistoryResponse(histories=history)

    async def handle_external_callback(
            self,
            node_instance_id_str: str,
            payload: Dict[str, Any],
    ) -> wt.CallbackAckResponse:
        """处理异步回调并继续运行 / Persist async callback payload then resume downstream nodes."""

        node_instance_id = uuid.UUID(node_instance_id_str)
        instance = await workflow_op.get_node_instance_by_id(node_instance_id)
        if not instance or instance.status != wt.NodeStatus.SUSPENDED:
            logger.warning("Callback received for non-suspended instance: %s", node_instance_id)
            return wt.CallbackAckResponse(status=CallbackAckStatus.IGNORED)

        await workflow_op.update_node_instance_result(
            node_instance_id,
            wt.NodeStatus.SUCCESS,
            final_output=self._serialize_output_payload(payload),
        )

        run = await workflow_op.get_workflow_run_by_id(instance.run_id)
        if not run:
            logger.error("Run %s not found while handling callback", instance.run_id)
            return wt.CallbackAckResponse(status=CallbackAckStatus.IGNORED)

        run_reqid = self._extract_reqid_from_run(run)
        set_request_id(run_reqid or None)

        workflow_def = await self._resolve_run_definition(run)
        if not workflow_def:
            logger.error("Workflow definition missing for run %s during callback", run.id)
            return wt.CallbackAckResponse(status=CallbackAckStatus.IGNORED)
        raw_node_config = workflow_def.nodes_config.get(instance.node_id)
        if not raw_node_config:
            logger.error("Node %s not found in workflow %s during callback", instance.node_id, workflow_def.id)
            return wt.CallbackAckResponse(status=CallbackAckStatus.IGNORED)
        node_config = wt.NodeConfig.model_validate(raw_node_config)

        for nid in node_config.next_node_ids or []:
            enqueue_node_execution(str(run.id), nid, instance.loop_index)

        return wt.CallbackAckResponse(status=CallbackAckStatus.ACCEPTED)

    async def get_workflow_stats(self) -> wt.WorkflowStats:
        """获取工作流统计数据 / Get workflow statistics."""
        return await workflow_op.get_workflow_stats()

    async def update_workflow_definition(
            self,
            workflow_id_str: str,
            data: wt.WorkflowDefinitionUpdate
    ) -> wt.WorkflowDefinition:
        """
        更新工作流定义（通过 domain 层，带分布式锁保护）
        Update workflow definition (via domain layer with distributed lock protection).

        Args:
            workflow_id_str: 工作流唯一标识符 / Workflow unique identifier.
            data: 更新数据 / Update data.

        Returns:
            更新后的工作流定义 / The updated workflow definition.
        """
        try:
            workflow_uuid = uuid.UUID(workflow_id_str)
        except ValueError:
            raise ParamError(f"Invalid workflow ID format: {workflow_id_str}")

        # 通过 domain 层调用，自动获取分布式锁
        # Call via domain layer, automatically acquires distributed lock
        updated = await workflow_domain.update_workflow_definition(workflow_uuid, data)
        if not updated:
            raise HTTPException(status_code=404, msg="Workflow not found")

        return updated

    async def delete_workflow_definition(self, workflow_id_str: str) -> None:
        """
        删除工作流定义（通过 domain 层，带分布式锁保护）
        Delete workflow definition (via domain layer with distributed lock protection).

        Args:
            workflow_id_str: 工作流唯一标识符 / Workflow unique identifier.
        """
        try:
            workflow_uuid = uuid.UUID(workflow_id_str)
        except ValueError:
            raise ParamError(f"Invalid workflow ID format: {workflow_id_str}")

        # 软删除：通过 domain 层设置 flag=1，自动获取分布式锁
        # Soft delete: set flag=1 via domain layer, automatically acquires distributed lock
        await workflow_domain.update_workflow_definition(
            workflow_uuid,
            wt.WorkflowDefinitionUpdate(flag=1)
        )

    async def rollback_workflow_definition(
            self,
            workflow_id_str: str,
            request: wt.WorkflowRollbackRequest,
    ) -> wt.WorkflowDefinition:
        """回滚工作流定义到指定版本
        Roll back a workflow definition to a target version."""

        try:
            workflow_uuid = uuid.UUID(workflow_id_str)
        except ValueError:
            raise ParamError(f"Invalid workflow ID format: {workflow_id_str}")

        updated = await workflow_domain.rollback_workflow_definition(
            workflow_uuid,
            target_version=request.target_version,
            reason=request.reason,
        )
        if not updated:
            raise HTTPException(status_code=404, msg="Workflow version not found")
        return updated

    async def list_engine_alerts(
            self,
            query: wt.WorkflowEngineAlertQuery,
    ) -> wt.WorkflowEngineAlertListResponse:
        """查询工作流引擎告警 / List workflow engine alerts for operators."""

        return await workflow_op.list_engine_alerts(query)

    async def acknowledge_engine_alert(
            self,
            alert_id_str: str,
            payload: wt.WorkflowEngineAlertAckRequest,
    ) -> wt.WorkflowEngineAlert:
        """标记引擎告警为已知晓 / Acknowledge an engine alert."""

        try:
            alert_id = uuid.UUID(alert_id_str)
        except ValueError:
            raise ParamError(f"Invalid alert ID format: {alert_id_str}")

        operator = (payload.operator or "ops_console").strip() or "ops_console"
        updated = await workflow_op.acknowledge_engine_alert(alert_id, operator, payload.note)
        if not updated:
            raise HTTPException(status_code=404, msg="Alert not found or already acknowledged")
        return updated

    async def resolve_engine_alert(
            self,
            alert_id_str: str,
            payload: wt.WorkflowEngineAlertAckRequest,
    ) -> wt.WorkflowEngineAlert:
        """标记引擎告警为已解决 / Resolve an engine alert."""

        try:
            alert_id = uuid.UUID(alert_id_str)
        except ValueError:
            raise ParamError(f"Invalid alert ID format: {alert_id_str}")

        operator = (payload.operator or "ops_console").strip() or "ops_console"
        updated = await workflow_op.resolve_engine_alert(alert_id, operator, payload.note)
        if not updated:
            raise HTTPException(status_code=404, msg="Alert not found or already resolved")
        return updated


workflow_app = WorkflowApp()

# Register inline orchestrator to avoid circular imports.
# 注册内联 orchestrator，避免 workflow_queue -> workflow_app 的循环依赖。
register_inline_orchestrator(workflow_app._execute_node_orchestrator)

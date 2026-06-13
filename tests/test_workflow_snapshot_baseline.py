"""Workflow orchestration/snapshot baseline tests.

这些测试固化 trigger、snapshot、orchestrator 的关键业务语义。
These tests lock trigger, snapshot, and orchestrator business semantics.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import (
    AsyncMock,
    Mock,
)

import pytest

from cancan_microstack.public.const.workflow_consts import WorkflowEngineAlertReason
from cancan_microstack.public.schemas.infra import workflow as wt
from cancan_microstack.services.infrasrv.application.workflow.workflow_app import WorkflowApp
from cancan_microstack.services.infrasrv.infrastructure.db.operate import workflow_op


def _build_sample_definition(version: int = 1) -> wt.WorkflowDefinition:
    """构造测试用工作流定义 / Build a workflow definition fixture for tests."""
    now = datetime.now(timezone.utc)
    start_node = wt.NodeConfig(
        id="start",
        name="Start",
        type=wt.NodeType.START,
        next_node_ids=["action"],
        config=wt.StartNodeConfig(),
    ).model_dump(mode="json")
    action_node = wt.NodeConfig(
        id="action",
        name="Action",
        type=wt.NodeType.ACTION,
        next_node_ids=[],
        config=wt.ActionNodeConfig(
            request=wt.RequestConfig(method="POST", url="http://example.com"),
        ),
    ).model_dump(mode="json")
    graph = wt.WorkflowGraphData(
        nodes=[
            wt.WorkflowGraphNode(
                node_id="start",
                label="Start",
                type=wt.NodeType.START,
                position=wt.VueFlowPosition(x=0, y=0),
            ),
            wt.WorkflowGraphNode(
                node_id="action",
                label="Action",
                type=wt.NodeType.ACTION,
                position=wt.VueFlowPosition(x=100, y=0),
            ),
        ],
        edges=[
            wt.WorkflowGraphEdge(
                id="start-action",
                source="start",
                target="action",
            ),
        ],
        version=version,
    )
    return wt.WorkflowDefinition(
        id=uuid.uuid4(),
        name="Demo",
        description="",
        schedule=None,
        graph_data=graph,
        nodes_config={
            "start": start_node,
            "action": action_node,
        },
        global_context={"env": "test"},
        is_active=True,
        flag=0,
        created_time=now,
        update_time=now,
        version=version,
    )


def _build_run(workflow: wt.WorkflowDefinition) -> wt.WorkflowRun:
    """生成绑定给定工作流的运行实例 / Create a workflow run linked to the provided definition."""
    now = datetime.now(timezone.utc)
    return wt.WorkflowRun(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        status=wt.WorkflowStatus.PENDING,
        trigger_type=wt.TriggerType.API,
        trigger_context={},
        global_context={},
        definition_version=workflow.version,
        definition_snapshot=None,
        started_at=now,
        finished_at=None,
        duration_ms=None,
        flag=0,
        created_time=now,
        update_time=now,
    )


def test_resolve_loop_reentry_controller_detects_body_tail_via_graph_subgraph():
    """当循环体存在多节点链路时，应识别尾节点属于循环体并回派 LOOP。
    Multi-step loop body tail nodes should resolve back to LOOP controller.
    """

    app = WorkflowApp()
    now = datetime.now(timezone.utc)
    workflow = wt.WorkflowDefinition(
        id=uuid.uuid4(),
        name="Loop Graph",
        description="",
        schedule=None,
        graph_data=wt.WorkflowGraphData(
            nodes=[
                wt.WorkflowGraphNode(node_id="loop", label="Loop", type=wt.NodeType.LOOP, position=wt.VueFlowPosition(x=0, y=0)),
                wt.WorkflowGraphNode(node_id="a", label="A", type=wt.NodeType.ACTION, position=wt.VueFlowPosition(x=100, y=0)),
                wt.WorkflowGraphNode(node_id="b", label="B", type=wt.NodeType.ACTION, position=wt.VueFlowPosition(x=200, y=0)),
                wt.WorkflowGraphNode(node_id="exit", label="Exit", type=wt.NodeType.END, position=wt.VueFlowPosition(x=300, y=0)),
            ],
            edges=[
                wt.WorkflowGraphEdge(id="e1", source="loop", target="a", sourceHandle="loop-body"),
                wt.WorkflowGraphEdge(id="e2", source="a", target="b"),
                wt.WorkflowGraphEdge(id="e3", source="loop", target="exit", sourceHandle="loop-exit"),
            ],
            version=1,
        ),
        nodes_config={
            "loop": wt.NodeConfig(
                id="loop",
                name="Loop",
                type=wt.NodeType.LOOP,
                next_node_ids=["exit"],
                config=wt.LoopNodeConfig(
                    condition="context.loop_index >= 3",
                    body_entry_id="a",
                    exit_node_id="exit",
                    max_iterations=5,
                ),
            ).model_dump(mode="json"),
            "a": wt.NodeConfig(
                id="a",
                name="A",
                type=wt.NodeType.ACTION,
                next_node_ids=["b"],
                config=wt.ActionNodeConfig(request=wt.RequestConfig(method="POST", url="http://example.com/a")),
            ).model_dump(mode="json"),
            "b": wt.NodeConfig(
                id="b",
                name="B",
                type=wt.NodeType.ACTION,
                next_node_ids=[],
                config=wt.ActionNodeConfig(request=wt.RequestConfig(method="POST", url="http://example.com/b")),
            ).model_dump(mode="json"),
            "exit": wt.NodeConfig(
                id="exit",
                name="Exit",
                type=wt.NodeType.END,
                config=wt.EndNodeConfig(status=wt.EndStatus.SUCCESS),
            ).model_dump(mode="json"),
        },
        global_context={},
        is_active=True,
        flag=0,
        created_time=now,
        update_time=now,
        version=1,
    )

    resolved = app._resolve_loop_reentry_controller(workflow_def=workflow, current_node_id="b")
    assert resolved == "loop"


def test_resolve_loop_reentry_controller_returns_none_outside_loop_body():
    """循环体外节点不应被误判为可回派节点。
    Nodes outside loop body must not be misclassified for loop reentry.
    """

    app = WorkflowApp()
    now = datetime.now(timezone.utc)
    workflow = wt.WorkflowDefinition(
        id=uuid.uuid4(),
        name="Loop Graph 2",
        description="",
        schedule=None,
        graph_data=wt.WorkflowGraphData(
            nodes=[
                wt.WorkflowGraphNode(node_id="loop", label="Loop", type=wt.NodeType.LOOP, position=wt.VueFlowPosition(x=0, y=0)),
                wt.WorkflowGraphNode(node_id="body", label="Body", type=wt.NodeType.ACTION, position=wt.VueFlowPosition(x=100, y=0)),
                wt.WorkflowGraphNode(node_id="other", label="Other", type=wt.NodeType.ACTION, position=wt.VueFlowPosition(x=250, y=100)),
            ],
            edges=[
                wt.WorkflowGraphEdge(id="e1", source="loop", target="body", sourceHandle="loop-body"),
            ],
            version=1,
        ),
        nodes_config={
            "loop": wt.NodeConfig(
                id="loop",
                name="Loop",
                type=wt.NodeType.LOOP,
                next_node_ids=[],
                config=wt.LoopNodeConfig(
                    condition="context.loop_index >= 3",
                    body_entry_id="body",
                    max_iterations=5,
                ),
            ).model_dump(mode="json"),
            "body": wt.NodeConfig(
                id="body",
                name="Body",
                type=wt.NodeType.ACTION,
                next_node_ids=[],
                config=wt.ActionNodeConfig(request=wt.RequestConfig(method="POST", url="http://example.com/body")),
            ).model_dump(mode="json"),
            "other": wt.NodeConfig(
                id="other",
                name="Other",
                type=wt.NodeType.ACTION,
                next_node_ids=[],
                config=wt.ActionNodeConfig(request=wt.RequestConfig(method="POST", url="http://example.com/other")),
            ).model_dump(mode="json"),
        },
        global_context={},
        is_active=True,
        flag=0,
        created_time=now,
        update_time=now,
        version=1,
    )

    resolved = app._resolve_loop_reentry_controller(workflow_def=workflow, current_node_id="other")
    assert resolved is None


@pytest.mark.asyncio
async def test_trigger_workflow_persists_definition_snapshot(monkeypatch):
    app = WorkflowApp()
    workflow = _build_sample_definition(version=3)

    async def fake_get_definition(self, workflow_id_str):
        return workflow

    run = _build_run(workflow)
    create_mock = AsyncMock(return_value=run)
    update_status_mock = AsyncMock()

    monkeypatch.setattr(WorkflowApp, "get_workflow_definition", fake_get_definition, raising=False)
    monkeypatch.setattr(workflow_op, "create_workflow_run", create_mock)
    monkeypatch.setattr(workflow_op, "update_workflow_run_status", update_status_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.get_request_id",
        lambda: "ctx-req-from-linglong",
    )
    set_request_id_mock = Mock()
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.set_request_id",
        set_request_id_mock,
    )
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.enqueue_node_execution",
        lambda *args, **kwargs: None,
    )

    payload = wt.WorkflowTriggerRequest(trigger_context={"foo": "bar"})
    response = await app.trigger_workflow(str(workflow.id), payload)

    awaited_payload = create_mock.await_args_list[0].args[0]
    assert awaited_payload.definition_version == workflow.version
    assert awaited_payload.definition_snapshot["version"] == workflow.version
    assert awaited_payload.definition_snapshot["nodes_config"]["start"]["id"] == "start"
    assert awaited_payload.trigger_context["reqid"] == "ctx-req-from-linglong"
    assert awaited_payload.global_context["reqid"] == "ctx-req-from-linglong"
    set_request_id_mock.assert_not_called()

    assert response.run_id == str(run.id)
    assert response.dispatch_status == wt.TriggerDispatchStatus.DISPATCHED

    update_status_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_workflow_preserves_existing_reqid(monkeypatch):
    app = WorkflowApp()
    workflow = _build_sample_definition(version=1)

    async def fake_get_definition(self, workflow_id_str):
        return workflow

    run = _build_run(workflow)
    create_mock = AsyncMock(return_value=run)
    update_status_mock = AsyncMock()

    monkeypatch.setattr(WorkflowApp, "get_workflow_definition", fake_get_definition, raising=False)
    monkeypatch.setattr(workflow_op, "create_workflow_run", create_mock)
    monkeypatch.setattr(workflow_op, "update_workflow_run_status", update_status_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.get_request_id",
        lambda: "ctx-req-should-not-override",
    )
    set_request_id_mock = Mock()
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.set_request_id",
        set_request_id_mock,
    )
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.enqueue_node_execution",
        lambda *args, **kwargs: None,
    )

    payload = wt.WorkflowTriggerRequest(trigger_context={"reqid": "custom-req-001"})
    await app.trigger_workflow(str(workflow.id), payload)

    awaited_payload = create_mock.await_args_list[0].args[0]
    assert awaited_payload.trigger_context["reqid"] == "custom-req-001"
    assert awaited_payload.global_context["reqid"] == "custom-req-001"
    set_request_id_mock.assert_called_once_with("custom-req-001")


@pytest.mark.asyncio
async def test_resolve_run_definition_prefers_snapshot(monkeypatch):
    app = WorkflowApp()
    workflow = _build_sample_definition(version=5)
    run = _build_run(workflow).model_copy(update={"definition_snapshot": workflow.model_dump(mode="json")})

    fetch_mock = AsyncMock()
    monkeypatch.setattr(workflow_op, "get_workflow_definition_by_id", fetch_mock)

    resolved = await app._resolve_run_definition(run)

    assert resolved is not None
    assert resolved.version == workflow.version
    fetch_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_node_orchestrator_marks_failure_when_non_end_has_no_downstream(monkeypatch):
    """非 END 节点成功但无下游时，运行应终止为 FAILURE 并发出告警。
    Successful non-END node without downstream should finalize run as FAILURE and emit alert.
    """

    app = WorkflowApp()
    workflow = _build_sample_definition(version=1)
    run = _build_run(workflow).model_copy(update={
        "status": wt.WorkflowStatus.RUNNING,
        "global_context": {"reqid": "req-dead-end"},
    })
    now = datetime.now(timezone.utc)
    instance = wt.NodeInstance(
        id=uuid.uuid4(),
        run_id=run.id,
        node_id="action",
        loop_index=1,
        status=wt.NodeStatus.PENDING,
        input_data={},
        final_output=None,
        attempt_count=1,
        error_msg=None,
        flag=0,
        created_time=now,
        update_time=now,
    )
    log_entry = wt.ExecutionLog(
        id=uuid.uuid4(),
        node_instance_id=instance.id,
        attempt_no=1,
        status=wt.ExecutionLogStatus.PENDING,
        request_snapshot={},
        response_snapshot=None,
        error_detail=None,
        duration_ms=None,
        started_at=now,
        finished_at=None,
        flag=0,
        created_time=now,
        update_time=now,
    )

    emit_alert_mock = AsyncMock()
    update_run_status_mock = AsyncMock()

    monkeypatch.setattr(app, "_resolve_run_definition", AsyncMock(return_value=workflow))
    monkeypatch.setattr(app, "_emit_engine_alert", emit_alert_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.set_request_id",
        lambda _: None,
    )
    monkeypatch.setattr(workflow_op, "get_workflow_run_by_id", AsyncMock(return_value=run))
    monkeypatch.setattr(workflow_op, "get_node_instances_by_run_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(workflow_op, "upsert_node_instance", AsyncMock(return_value=instance))
    monkeypatch.setattr(workflow_op, "create_execution_log", AsyncMock(return_value=log_entry))
    monkeypatch.setattr(workflow_op, "update_node_instance_result", AsyncMock())
    monkeypatch.setattr(
        workflow_op,
        "update_workflow_run_global_context",
        AsyncMock(return_value=run.model_copy(update={"global_context": {"reqid": "req-dead-end", "__runtime__": {}}})),
    )
    monkeypatch.setattr(workflow_op, "update_execution_log_result", AsyncMock())
    monkeypatch.setattr(workflow_op, "update_workflow_run_status", update_run_status_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.enqueue_node_execution",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.workflow_engine.process_node",
        AsyncMock(return_value=({"ok": True}, wt.NodeStatus.SUCCESS, [], 1)),
    )

    await app._execute_node_orchestrator(str(run.id), "action", 1)

    emit_alert_mock.assert_awaited_once()
    emitted_reason = emit_alert_mock.await_args.kwargs.get("reason")
    assert emitted_reason == WorkflowEngineAlertReason.NODE_TERMINATED_WITHOUT_DOWNSTREAM
    assert any(
        call.args == (run.id, wt.WorkflowStatus.FAILURE)
        for call in update_run_status_mock.await_args_list
    )


@pytest.mark.asyncio
async def test_execute_node_orchestrator_reenters_loop_when_body_entry_has_no_downstream(monkeypatch):
    """LOOP 的 body_entry 节点无显式下游时，应自动回派 LOOP 控制节点。
    Loop body entry node without explicit downstream should dispatch back to LOOP controller.
    """

    app = WorkflowApp()
    workflow = _build_sample_definition(version=1)
    loop_node = wt.NodeConfig(
        id="loop",
        name="Loop",
        type=wt.NodeType.LOOP,
        config=wt.LoopNodeConfig(
            condition="context.loop_index >= 3",
            body_entry_id="action",
            max_iterations=5,
        ),
    ).model_dump(mode="json")
    action_node = wt.NodeConfig(
        id="action",
        name="Action",
        type=wt.NodeType.ACTION,
        config=wt.ActionNodeConfig(
            request=wt.RequestConfig(method="POST", url="http://example.com"),
        ),
        next_node_ids=[],
    ).model_dump(mode="json")
    workflow = workflow.model_copy(update={"nodes_config": {"loop": loop_node, "action": action_node}})

    run = _build_run(workflow).model_copy(update={
        "status": wt.WorkflowStatus.RUNNING,
        "global_context": {"reqid": "req-loop-reentry"},
    })
    now = datetime.now(timezone.utc)
    instance = wt.NodeInstance(
        id=uuid.uuid4(),
        run_id=run.id,
        node_id="action",
        loop_index=2,
        status=wt.NodeStatus.PENDING,
        input_data={},
        final_output=None,
        attempt_count=1,
        error_msg=None,
        flag=0,
        created_time=now,
        update_time=now,
    )
    log_entry = wt.ExecutionLog(
        id=uuid.uuid4(),
        node_instance_id=instance.id,
        attempt_no=1,
        status=wt.ExecutionLogStatus.PENDING,
        request_snapshot={},
        response_snapshot=None,
        error_detail=None,
        duration_ms=None,
        started_at=now,
        finished_at=None,
        flag=0,
        created_time=now,
        update_time=now,
    )

    emit_alert_mock = AsyncMock()
    update_run_status_mock = AsyncMock()
    enqueue_mock = Mock()

    monkeypatch.setattr(app, "_resolve_run_definition", AsyncMock(return_value=workflow))
    monkeypatch.setattr(app, "_emit_engine_alert", emit_alert_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.set_request_id",
        lambda _: None,
    )
    monkeypatch.setattr(workflow_op, "get_workflow_run_by_id", AsyncMock(return_value=run))
    monkeypatch.setattr(workflow_op, "get_node_instances_by_run_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(workflow_op, "upsert_node_instance", AsyncMock(return_value=instance))
    monkeypatch.setattr(workflow_op, "create_execution_log", AsyncMock(return_value=log_entry))
    monkeypatch.setattr(workflow_op, "update_node_instance_result", AsyncMock())
    monkeypatch.setattr(
        workflow_op,
        "update_workflow_run_global_context",
        AsyncMock(return_value=run.model_copy(update={"global_context": {"reqid": "req-loop-reentry"}})),
    )
    monkeypatch.setattr(workflow_op, "update_execution_log_result", AsyncMock())
    monkeypatch.setattr(workflow_op, "update_workflow_run_status", update_run_status_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.enqueue_node_execution",
        enqueue_mock,
    )
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.workflow_engine.process_node",
        AsyncMock(return_value=({"ok": True}, wt.NodeStatus.SUCCESS, [], 2)),
    )

    await app._execute_node_orchestrator(str(run.id), "action", 2)

    enqueue_mock.assert_called_once_with(str(run.id), "loop", 3)
    emit_alert_mock.assert_not_awaited()
    assert not any(
        call.args == (run.id, wt.WorkflowStatus.FAILURE)
        for call in update_run_status_mock.await_args_list
    )


@pytest.mark.asyncio
async def test_execute_node_orchestrator_reenters_loop_when_body_tail_has_no_downstream(monkeypatch):
    """循环体为多节点链路时，尾节点无下游也应回派 LOOP 控制节点。
    For multi-step loop body chains, tail node dead-end should still re-dispatch LOOP controller.
    """

    app = WorkflowApp()
    workflow = _build_sample_definition(version=1)
    graph = wt.WorkflowGraphData(
        nodes=[
            wt.WorkflowGraphNode(node_id="loop", label="Loop", type=wt.NodeType.LOOP, position=wt.VueFlowPosition(x=0, y=0)),
            wt.WorkflowGraphNode(node_id="action-a", label="Action A", type=wt.NodeType.ACTION, position=wt.VueFlowPosition(x=120, y=0)),
            wt.WorkflowGraphNode(node_id="action-b", label="Action B", type=wt.NodeType.ACTION, position=wt.VueFlowPosition(x=260, y=0)),
            wt.WorkflowGraphNode(node_id="exit", label="Exit", type=wt.NodeType.END, position=wt.VueFlowPosition(x=420, y=0)),
        ],
        edges=[
            wt.WorkflowGraphEdge(id="loop-body", source="loop", target="action-a", sourceHandle="loop-body"),
            wt.WorkflowGraphEdge(id="loop-exit", source="loop", target="exit", sourceHandle="loop-exit"),
            wt.WorkflowGraphEdge(id="body-chain", source="action-a", target="action-b"),
        ],
        version=1,
    )
    workflow = workflow.model_copy(update={
        "graph_data": graph,
        "nodes_config": {
            "loop": wt.NodeConfig(
                id="loop",
                name="Loop",
                type=wt.NodeType.LOOP,
                next_node_ids=["exit"],
                config=wt.LoopNodeConfig(
                    condition="context.loop_index >= 3",
                    body_entry_id="action-a",
                    exit_node_id="exit",
                    max_iterations=5,
                ),
            ).model_dump(mode="json"),
            "action-a": wt.NodeConfig(
                id="action-a",
                name="Action A",
                type=wt.NodeType.ACTION,
                next_node_ids=["action-b"],
                config=wt.ActionNodeConfig(request=wt.RequestConfig(method="POST", url="http://example.com/a")),
            ).model_dump(mode="json"),
            "action-b": wt.NodeConfig(
                id="action-b",
                name="Action B",
                type=wt.NodeType.ACTION,
                next_node_ids=[],
                config=wt.ActionNodeConfig(request=wt.RequestConfig(method="POST", url="http://example.com/b")),
            ).model_dump(mode="json"),
            "exit": wt.NodeConfig(
                id="exit",
                name="Exit",
                type=wt.NodeType.END,
                config=wt.EndNodeConfig(status=wt.EndStatus.SUCCESS),
            ).model_dump(mode="json"),
        },
    })

    run = _build_run(workflow).model_copy(update={
        "status": wt.WorkflowStatus.RUNNING,
        "global_context": {"reqid": "req-loop-tail-reentry"},
    })
    now = datetime.now(timezone.utc)
    instance = wt.NodeInstance(
        id=uuid.uuid4(),
        run_id=run.id,
        node_id="action-b",
        loop_index=2,
        status=wt.NodeStatus.PENDING,
        input_data={},
        final_output=None,
        attempt_count=1,
        error_msg=None,
        flag=0,
        created_time=now,
        update_time=now,
    )
    log_entry = wt.ExecutionLog(
        id=uuid.uuid4(),
        node_instance_id=instance.id,
        attempt_no=1,
        status=wt.ExecutionLogStatus.PENDING,
        request_snapshot={},
        response_snapshot=None,
        error_detail=None,
        duration_ms=None,
        started_at=now,
        finished_at=None,
        flag=0,
        created_time=now,
        update_time=now,
    )

    emit_alert_mock = AsyncMock()
    update_run_status_mock = AsyncMock()
    enqueue_mock = Mock()

    monkeypatch.setattr(app, "_resolve_run_definition", AsyncMock(return_value=workflow))
    monkeypatch.setattr(app, "_emit_engine_alert", emit_alert_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.set_request_id",
        lambda _: None,
    )
    monkeypatch.setattr(workflow_op, "get_workflow_run_by_id", AsyncMock(return_value=run))
    monkeypatch.setattr(workflow_op, "get_node_instances_by_run_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(workflow_op, "upsert_node_instance", AsyncMock(return_value=instance))
    monkeypatch.setattr(workflow_op, "create_execution_log", AsyncMock(return_value=log_entry))
    monkeypatch.setattr(workflow_op, "update_node_instance_result", AsyncMock())
    monkeypatch.setattr(
        workflow_op,
        "update_workflow_run_global_context",
        AsyncMock(return_value=run.model_copy(update={"global_context": {"reqid": "req-loop-tail-reentry"}})),
    )
    monkeypatch.setattr(workflow_op, "update_execution_log_result", AsyncMock())
    monkeypatch.setattr(workflow_op, "update_workflow_run_status", update_run_status_mock)
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.enqueue_node_execution",
        enqueue_mock,
    )
    monkeypatch.setattr(
        "cancan_microstack.services.infrasrv.application.workflow.workflow_app.workflow_engine.process_node",
        AsyncMock(return_value=({"ok": True}, wt.NodeStatus.SUCCESS, [], 2)),
    )

    await app._execute_node_orchestrator(str(run.id), "action-b", 2)

    enqueue_mock.assert_called_once_with(str(run.id), "loop", 3)
    emit_alert_mock.assert_not_awaited()
    assert not any(
        call.args == (run.id, wt.WorkflowStatus.FAILURE)
        for call in update_run_status_mock.await_args_list
    )


@pytest.mark.asyncio
async def test_get_run_graph_status_serializes_node_config_model_snapshot(monkeypatch):
    """节点快照应支持 NodeConfig 模型并序列化为运行时 JSON。
    Node config snapshot should serialize NodeConfig models into runtime JSON payload.
    """

    app = WorkflowApp()
    workflow = _build_sample_definition(version=2)
    workflow.nodes_config["action"] = wt.NodeConfig(
        id="action",
        name="Action",
        type=wt.NodeType.ACTION,
        next_node_ids=[],
        config=wt.ActionNodeConfig(
            request=wt.RequestConfig(method="POST", url="http://example.com"),
        ),
    )
    run = _build_run(workflow)

    monkeypatch.setattr(workflow_op, "get_workflow_run_by_id", AsyncMock(return_value=run))
    monkeypatch.setattr(app, "_resolve_run_definition", AsyncMock(return_value=workflow))
    monkeypatch.setattr(workflow_op, "get_node_instances_by_run_id", AsyncMock(return_value=[]))

    graph = await app.get_run_graph_status(str(run.id))
    action_node = next(node for node in graph.nodes if node.node_id == "action")

    assert action_node.node_config_snapshot is not None
    assert action_node.node_config_snapshot["id"] == "action"
    assert action_node.node_config_snapshot["type"] == wt.NodeType.ACTION.value

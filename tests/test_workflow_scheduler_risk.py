"""Workflow scheduler risk-oriented tests.

聚焦调度容错与隔离语义，而非仅覆盖率。
Focus on scheduler fault-tolerance and isolation semantics, not line coverage only.
"""

import uuid
from datetime import datetime

import pytest

from cancan_microstack.public.schemas.infra import workflow as workflow_types
from cancan_microstack.public.schemas.infra.enums import TriggerType
from cancan_microstack.services.infrasrv.interface.schedule import workflow_scheduler


class DummyWorkflow:
    """简化工作流定义桩 / Lightweight workflow definition stub."""

    def __init__(self, schedule: str, name: str = "WF"):
        self.id = uuid.uuid4()
        self.name = name
        self.schedule = schedule
        self.nodes_config = {}


@pytest.mark.asyncio
async def test_scheduler_skips_invalid_or_empty_cron(monkeypatch):
    """空 cron 与非法 cron 都应被安全跳过，不触发执行。
    Empty/invalid cron entries must be safely skipped without dispatch.
    """

    workflows = [
        DummyWorkflow("", name="empty"),
        DummyWorkflow("invalid cron", name="invalid"),
    ]
    triggered = []

    async def fake_get_workflows():
        return workflows

    async def fake_trigger(workflow_id_str: str, payload: workflow_types.WorkflowTriggerRequest, trigger_type: TriggerType):
        triggered.append((workflow_id_str, payload, trigger_type))
        return workflow_types.WorkflowTriggerResponse(
            run_id="run-invalid",
            dispatch_status=workflow_types.TriggerDispatchStatus.DISPATCHED,
        )

    monkeypatch.setattr(workflow_scheduler.workflow_app, "get_scheduled_workflows", fake_get_workflows)
    monkeypatch.setattr(workflow_scheduler.workflow_app, "trigger_workflow", fake_trigger)

    await workflow_scheduler.scan_and_trigger_workflows(reference_time=datetime(2026, 2, 22, 10, 0, 0))

    assert triggered == []


@pytest.mark.asyncio
async def test_scheduler_continues_when_one_trigger_fails(monkeypatch):
    """单个工作流触发失败不应阻断同批次其他工作流。
    One workflow trigger failure must not block other workflows in same scan.
    """

    workflow_a = DummyWorkflow("10 * * * *", name="A")
    workflow_b = DummyWorkflow("10 * * * *", name="B")
    triggered = []

    async def fake_get_workflows():
        return [workflow_a, workflow_b]

    async def fake_trigger(workflow_id_str: str, payload: workflow_types.WorkflowTriggerRequest, trigger_type: TriggerType):
        if workflow_id_str == str(workflow_a.id):
            raise RuntimeError("intentional-trigger-failure")
        triggered.append(
            {
                "workflow_id": workflow_id_str,
                "trigger_type": trigger_type,
                "reqid": payload.trigger_context.get("reqid"),
            }
        )
        return workflow_types.WorkflowTriggerResponse(
            run_id="run-ok",
            dispatch_status=workflow_types.TriggerDispatchStatus.DISPATCHED,
        )

    monkeypatch.setattr(workflow_scheduler.workflow_app, "get_scheduled_workflows", fake_get_workflows)
    monkeypatch.setattr(workflow_scheduler.workflow_app, "trigger_workflow", fake_trigger)

    await workflow_scheduler.scan_and_trigger_workflows(reference_time=datetime(2026, 2, 22, 10, 10, 0))

    assert len(triggered) == 1
    assert triggered[0]["workflow_id"] == str(workflow_b.id)
    assert triggered[0]["trigger_type"] == TriggerType.SCHEDULE
    assert isinstance(triggered[0]["reqid"], str) and triggered[0]["reqid"].strip()


@pytest.mark.asyncio
async def test_scheduler_sets_scheduled_time_in_trigger_context(monkeypatch):
    """触发上下文应包含规范化 scheduled_time，便于追踪。
    Trigger context must include normalized scheduled_time for observability.
    """

    workflow = DummyWorkflow("5 0 10 * * *", name="seconds-cron")
    captured = {}

    async def fake_get_workflows():
        return [workflow]

    async def fake_trigger(workflow_id_str: str, payload: workflow_types.WorkflowTriggerRequest, trigger_type: TriggerType):
        captured["workflow_id"] = workflow_id_str
        captured["trigger_type"] = trigger_type
        captured["scheduled_time"] = payload.trigger_context.get("scheduled_time")
        return workflow_types.WorkflowTriggerResponse(
            run_id="run-seconds",
            dispatch_status=workflow_types.TriggerDispatchStatus.DISPATCHED,
        )

    monkeypatch.setattr(workflow_scheduler.workflow_app, "get_scheduled_workflows", fake_get_workflows)
    monkeypatch.setattr(workflow_scheduler.workflow_app, "trigger_workflow", fake_trigger)

    now = datetime(2026, 2, 22, 10, 0, 5)
    await workflow_scheduler.scan_and_trigger_workflows(reference_time=now)

    assert captured["workflow_id"] == str(workflow.id)
    assert captured["trigger_type"] == TriggerType.SCHEDULE
    assert captured["scheduled_time"] == now.replace(microsecond=0).isoformat()

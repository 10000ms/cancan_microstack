"""WorkflowOpsApp baseline tests.

固化 ops 层对 infrasrv 协议的严格语义与模型约束行为。
Lock strict ops/infrasrv contract semantics and model constraints.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.schemas.common import (
    APIError,
    APIResponse,
)
from cancan_microstack.public.schemas.infra import workflow as wt
from cancan_microstack.public.schemas.infra.enums import NodeType
from cancan_microstack.services.opsbffsrv.application.workflow_ops_app import WorkflowOpsApp
from linglong_web import LinglongConfig


def _ensure_ops_config_defaults() -> None:
    """为单测注入最小必要配置 / Ensure minimal config keys for unit tests."""
    LinglongConfig.apply_updates({
        "INFRASRV_HOST": "http://infrasrv.service:8080",
    })


class _FakeInfraClient:
    def __init__(self, response: APIResponse[Any]):
        self._response = response

    async def list_workflow_definitions(self, *args, **kwargs) -> APIResponse[Any]:
        return self._response


class _FakeGraphInfraClient:
    def __init__(self, response: APIResponse[Any]):
        self._response = response

    async def get_run_graph_status(self, run_id: str) -> APIResponse[Any]:
        return self._response


class _FakeDetailInfraClient:
    def __init__(self, response: APIResponse[Any]):
        self._response = response

    async def get_workflow_definition(self, workflow_id: str) -> APIResponse[Any]:
        return self._response


def _build_workflow(nodes_config: dict[str, wt.NodeConfig]) -> wt.WorkflowDefinition:
    now = datetime.now(timezone.utc)
    return wt.WorkflowDefinition(
        id=uuid.uuid4(),
        name="Ops Flow",
        description="Daily ops flow",
        schedule=None,
        graph_data=wt.WorkflowGraphData(),
        nodes_config=nodes_config,
        global_context={"tags": ["Ops", "Flow"]},
        is_active=True,
        flag=0,
        created_time=now,
        update_time=now,
    )


@pytest.mark.asyncio
async def test_list_workflows_accepts_pydantic_payload() -> None:
    workflow_model = wt.WorkflowDefinition(
        id=uuid.uuid4(),
        name="Ops Flow",
        description="Daily ops flow",
        schedule=None,
        graph_data=wt.WorkflowGraphData(),
        nodes_config={},
        global_context={"tags": ["Ops", "Flow"]},
        is_active=True,
        flag=0,
        created_time=datetime.now(timezone.utc),
        update_time=datetime.now(timezone.utc),
    )
    payload = wt.WorkflowListResponse(list=[workflow_model], total=1, page=1, page_size=20)
    api_response = APIResponse(success=True, error=APIError(code="0", msg=""), data=payload)

    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()
    app.infra_client = _FakeInfraClient(api_response)

    result = await app.list_workflows(wt.WorkflowListQuery(keyword="ops"))

    assert len(result.list) == 1
    assert result.list[0] is workflow_model
    assert result.total == 1


@pytest.mark.asyncio
async def test_validate_workflow_accepts_nodeconfig_models() -> None:
    nodes = {
        "start": wt.NodeConfig(
            id="start",
            name="Start",
            type=NodeType.START,
            next_node_id="end",
        ),
        "end": wt.NodeConfig(
            id="end",
            name="End",
            type=NodeType.END,
        ),
    }
    workflow = _build_workflow(nodes)

    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()

    async def _fake_get_workflow(_: str) -> wt.WorkflowDefinition:
        return workflow

    app.get_workflow = _fake_get_workflow  # type: ignore[assignment]

    result = await app.validate_workflow("wf-test")

    assert result["valid"] is True
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_validate_workflow_flags_missing_next_nodes() -> None:
    nodes = {
        "start": wt.NodeConfig(
            id="start",
            name="Start",
            type=NodeType.START,
            next_node_id="ghost",
        ),
        "end": wt.NodeConfig(
            id="end",
            name="End",
            type=NodeType.END,
        ),
    }
    workflow = _build_workflow(nodes)

    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()

    async def _fake_get_workflow(_: str) -> wt.WorkflowDefinition:
        return workflow

    app.get_workflow = _fake_get_workflow  # type: ignore[assignment]

    result = await app.validate_workflow("wf-missing")

    assert result["valid"] is False
    assert "Node start references non-existent node ghost" in result["issues"]


@pytest.mark.asyncio
async def test_get_run_graph_status_maps_only_exact_404_to_not_found() -> None:
    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()
    app.infra_client = _FakeGraphInfraClient(
        APIResponse(success=False, error=APIError(code="404", msg="Run not found"), data=None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await app.get_run_graph_status("run-404")

    assert getattr(exc_info.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_get_run_graph_status_non_404_code_returns_500() -> None:
    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()
    app.infra_client = _FakeGraphInfraClient(
        APIResponse(success=False, error=APIError(code="4040", msg="Run not found (non-404 code)"), data=None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await app.get_run_graph_status("run-4040")

    assert getattr(exc_info.value, "status_code", None) == 500


@pytest.mark.asyncio
async def test_get_workflow_maps_exact_404_to_not_found() -> None:
    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()
    app.infra_client = _FakeDetailInfraClient(
        APIResponse(success=False, error=APIError(code="404", msg="Not found"), data=None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await app.get_workflow("wf-404")

    assert getattr(exc_info.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_get_workflow_non_404_code_returns_500() -> None:
    _ensure_ops_config_defaults()
    app = WorkflowOpsApp()
    app.infra_client = _FakeDetailInfraClient(
        APIResponse(success=False, error=APIError(code="4040", msg="Not found (non-404 code)"), data=None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await app.get_workflow("wf-4040")

    assert getattr(exc_info.value, "status_code", None) == 500

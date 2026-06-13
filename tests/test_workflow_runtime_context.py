import uuid

from cancan_microstack.public.schemas.infra.enums import NodeType
from cancan_microstack.public.schemas.infra.enums import NodeStatus
from cancan_microstack.public.schemas.infra.workflow import ActionNodeConfig
from cancan_microstack.public.schemas.infra.workflow import NodeConfig
from cancan_microstack.public.schemas.infra.workflow import RequestConfig
from cancan_microstack.public.schemas.infra.workflow import WorkflowExecutionContext
from cancan_microstack.services.infrasrv.application.workflow.workflow_app import WorkflowApp
from cancan_microstack.services.infrasrv.domain.workflow.node_handlers import NodeHandler


def test_merge_runtime_context_records_latest_output_and_status():
    base_context = {
        "tenant": "demo",
        "__runtime__": {
            "node_outputs": {
                "node-a": {
                    "status": "SUCCESS",
                    "output": {"ok": True},
                },
            },
        },
    }

    merged = WorkflowApp._merge_runtime_context(
        current_context=base_context,
        node_id="node-b",
        node_status=NodeStatus.SUCCESS,
        output={"status_code": 200, "json_body": {"code": 0}},
    )

    assert merged["tenant"] == "demo"
    assert merged["__runtime__"]["last_node_id"] == "node-b"
    assert merged["__runtime__"]["last_status"] == NodeStatus.SUCCESS.value
    assert merged["__runtime__"]["last_output"]["status_code"] == 200
    assert merged["__runtime__"]["node_outputs"]["node-a"]["status"] == "SUCCESS"
    assert merged["__runtime__"]["node_outputs"]["node-b"]["output"]["json_body"]["code"] == 0


def test_template_context_contains_context_alias_and_flat_fields():
    ctx = WorkflowExecutionContext(
        run_id=uuid.uuid4(),
        global_context={"env": "dev"},
        nodes={},
        loop_index=3,
    )

    payload = NodeHandler._build_template_context(ctx)

    assert "context" in payload
    assert payload["context"]["global_context"]["env"] == "dev"
    assert payload["context"]["env"] == "dev"
    assert payload["loop_index"] == 3


def test_apply_action_context_mappings_sets_business_keys():
    node_config = NodeConfig(
        id="action-a",
        name="HTTP 请求",
        type=NodeType.ACTION,
        config=ActionNodeConfig(
            request=RequestConfig(url="https://example.com"),
            context_mappings={
                "biz.user_id": "json_body.data.user.id",
                "biz.amount": "json_body.data.amount",
                "api_ok": "ok",
            },
        ),
    )

    updated = WorkflowApp._apply_action_context_mappings(
        current_context={"tenant": "demo"},
        node_config=node_config,
        output={
            "ok": True,
            "json_body": {
                "data": {
                    "user": {"id": "u-001"},
                    "amount": 99,
                },
            },
        },
    )

    assert updated["tenant"] == "demo"
    assert updated["biz"]["user_id"] == "u-001"
    assert updated["biz"]["amount"] == 99
    assert updated["api_ok"] is True

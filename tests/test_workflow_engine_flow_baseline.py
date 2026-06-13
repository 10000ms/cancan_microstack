"""Workflow engine flow baseline tests.

这些测试固化当前 WorkflowEngine 的核心行为，作为 cancan_microstack 基线。
These tests lock the current WorkflowEngine core behavior as cancan_microstack baseline.
"""

import unittest
import uuid
from datetime import (
    datetime,
    timezone,
)
from unittest.mock import (
    AsyncMock,
    patch,
)

from cancan_microstack.public.schemas.infra.enums import (
    NodeStatus,
    NodeType,
)
from cancan_microstack.public.schemas.infra.workflow import (
    ActionNodeConfig,
    HttpResponseOutput,
    LogicNodeConfig,
    LoopNodeConfig,
    NodeConfig,
    RequestConfig,
    WorkflowDefinition,
    WorkflowExecutionContext,
)
from cancan_microstack.services.infrasrv.domain.workflow.engine import WorkflowEngine


class TestWorkflowEngineBaseline(unittest.IsolatedAsyncioTestCase):
    async def test_process_node_dispatches_handler_and_returns_next_node_ids(self):
        engine = WorkflowEngine()

        node = NodeConfig(
            id="step1",
            name="Step 1",
            type=NodeType.ACTION,
            next_node_ids=["step2"],
            config=ActionNodeConfig(
                request=RequestConfig(method="GET", url="http://example.com"),
            ),
        )
        now = datetime.now(timezone.utc)
        workflow_def = WorkflowDefinition(
            id=uuid.uuid4(),
            name="Demo",
            description=None,
            schedule=None,
            nodes_config={"step1": node},
            global_context={},
            is_active=True,
            flag=0,
            created_time=now,
            update_time=now,
        )

        context = WorkflowExecutionContext(run_id=uuid.uuid4())

        fake_output = HttpResponseOutput(
            status_code=200,
            headers={},
            text="ok",
            json_body={"ok": True},
            ok=True,
        )

        with patch(
            "cancan_microstack.services.infrasrv.domain.workflow.engine.ActionNodeHandler"
        ) as handler_cls:
            handler_instance = handler_cls.return_value
            handler_instance.process = AsyncMock(return_value=(fake_output, NodeStatus.SUCCESS))

            output, status, next_node_ids, loop_index = await engine.process_node(
                workflow_def,
                node,
                context,
            )

        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(next_node_ids, ["step2"])
        self.assertEqual(loop_index, 1)
        self.assertEqual(output.status_code, 200)

    async def test_determine_next_nodes_with_structured_logic_output(self):
        engine = WorkflowEngine()
        node = NodeConfig(
            id="logic-1",
            name="Logic",
            type=NodeType.LOGIC,
            config=LogicNodeConfig(
                condition="context.global_context.a > 0",
                true_next_node_id="true-branch",
                false_next_node_id="false-branch",
            ),
        )

        next_true, _ = engine._determine_next_nodes(node, {"result": True}, 1)
        next_false, _ = engine._determine_next_nodes(node, {"result": False}, 1)

        self.assertEqual(next_true, ["true-branch"])
        self.assertEqual(next_false, ["false-branch"])

    async def test_determine_next_nodes_with_loop_exit_condition(self):
        engine = WorkflowEngine()
        node = NodeConfig(
            id="loop-1",
            name="Loop",
            type=NodeType.LOOP,
            next_node_ids=["exit-node"],
            config=LoopNodeConfig(
                condition="context.loop_index >= 3",
                body_entry_id="body-node",
                exit_node_id="exit-node",
                max_iterations=10,
            ),
        )

        continue_next, continue_index = engine._determine_next_nodes(
            node,
            {"exit_condition_met": False},
            2,
        )
        exit_next, exit_index = engine._determine_next_nodes(
            node,
            {"exit_condition_met": True},
            3,
        )

        self.assertEqual(continue_next, ["body-node"])
        self.assertEqual(continue_index, 2)
        self.assertEqual(exit_next, ["exit-node"])
        self.assertEqual(exit_index, 3)


if __name__ == "__main__":
    unittest.main()

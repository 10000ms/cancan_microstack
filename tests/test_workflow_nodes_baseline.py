"""Workflow node handler baseline tests.

这些测试固化节点处理器关键行为，作为 cancan_microstack 基线。
These tests lock critical node-handler behavior as cancan_microstack baseline.
"""

import unittest
import uuid
from unittest.mock import (
    AsyncMock,
    patch,
)

import aiohttp

from cancan_microstack.public.schemas.infra.enums import (
    NodeStatus,
    NodeType,
)
from cancan_microstack.public.schemas.infra.workflow import (
    ActionNodeConfig,
    LogicNodeConfig,
    LoopNodeConfig,
    NodeConfig,
    NodeOutput,
    RequestConfig,
    TransformNodeConfig,
    WorkflowExecutionContext,
)
from cancan_microstack.services.infrasrv.domain.workflow.node_handlers import (
    ActionNodeHandler,
    LogicNodeHandler,
    LoopNodeHandler,
    TransformNodeHandler,
)


class TestNodeHandlersBaseline(unittest.IsolatedAsyncioTestCase):
    @patch("cancan_microstack.services.infrasrv.domain.workflow.node_handlers.http_client.fetch")
    async def test_action_node_renders_templates_and_calls_http(self, mock_fetch):
        cfg = NodeConfig(
            id="act",
            name="Action",
            type=NodeType.ACTION,
            config=ActionNodeConfig(
                request=RequestConfig(
                    method="POST",
                    url="http://test.com/{{ global_context.item_id }}",
                    headers={"H": "{{ global_context.header_val }}"},
                    body={"key": "{{ global_context.value }}"},
                ),
            ),
        )
        handler = ActionNodeHandler(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.ok = True
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = AsyncMock(return_value='{"ok": true}')
        mock_resp.json = AsyncMock(return_value={"ok": True})
        mock_fetch.return_value = mock_resp

        context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            global_context={
                "item_id": "123",
                "value": "v1",
                "header_val": "h1",
            },
        )

        output, status = await handler.process(context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(output.status_code, 200)
        self.assertEqual(output.json_body, {"ok": True})

        mock_fetch.assert_awaited_once()
        _, kwargs = mock_fetch.await_args
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["url"], "http://test.com/123")
        self.assertEqual(kwargs["headers"].get("H"), "h1")
        self.assertEqual(kwargs["headers"].get("Content-Type"), "application/json")
        self.assertEqual(kwargs["json"], {"key": "v1"})

    @patch("cancan_microstack.services.infrasrv.domain.workflow.node_handlers.http_client.fetch")
    async def test_action_node_supports_input_from_previous_node_output(self, mock_fetch):
        cfg = NodeConfig(
            id="act-prev",
            name="ActionPrev",
            type=NodeType.ACTION,
            config=ActionNodeConfig(
                request=RequestConfig(
                    method="GET",
                    url="http://test.com/users/{{ context.nodes['action-a'].output.json_body.data.user_id }}",
                    params={"trace": "{{ context.global_context.reqid }}"},
                ),
            ),
        )
        handler = ActionNodeHandler(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.ok = True
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = AsyncMock(return_value='{"ok": true}')
        mock_resp.json = AsyncMock(return_value={"ok": True})
        mock_fetch.return_value = mock_resp

        context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            global_context={"reqid": "req-001"},
            nodes={
                "action-a": NodeOutput(
                    output={"json_body": {"data": {"user_id": "u-001"}}},
                    status=NodeStatus.SUCCESS,
                ),
            },
        )

        _, status = await handler.process(context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        _, kwargs = mock_fetch.await_args
        self.assertEqual(kwargs["url"], "http://test.com/users/u-001")
        self.assertEqual(kwargs["params"], {"trace": "req-001"})

    @patch("cancan_microstack.services.infrasrv.domain.workflow.node_handlers.http_client.fetch")
    async def test_action_node_form_urlencoded_body_auto_header(self, mock_fetch):
        cfg = NodeConfig(
            id="act-form",
            name="ActionForm",
            type=NodeType.ACTION,
            config=ActionNodeConfig(
                request=RequestConfig(
                    method="POST",
                    url="http://test.com/form",
                    body_type="form-urlencoded",
                    form_body={"name": "{{ global_context.name }}"},
                ),
            ),
        )
        handler = ActionNodeHandler(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.ok = True
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = AsyncMock(return_value='{"ok": true}')
        mock_resp.json = AsyncMock(return_value={"ok": True})
        mock_fetch.return_value = mock_resp

        context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            global_context={"name": "alice"},
        )

        _, status = await handler.process(context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        _, kwargs = mock_fetch.await_args
        self.assertEqual(kwargs["headers"].get("Content-Type"), "application/x-www-form-urlencoded")
        self.assertEqual(kwargs["data"], {"name": "alice"})
        self.assertIsNone(kwargs["json"])

    @patch("cancan_microstack.services.infrasrv.domain.workflow.node_handlers.http_client.fetch")
    async def test_action_node_multipart_body_uses_form_data(self, mock_fetch):
        cfg = NodeConfig(
            id="act-multipart",
            name="ActionMultipart",
            type=NodeType.ACTION,
            config=ActionNodeConfig(
                request=RequestConfig(
                    method="POST",
                    url="http://test.com/upload",
                    body_type="multipart",
                    headers={"Content-Type": "multipart/form-data"},
                    form_body={"field": "{{ global_context.field }}"},
                ),
            ),
        )
        handler = ActionNodeHandler(cfg)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.ok = True
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = AsyncMock(return_value='{"ok": true}')
        mock_resp.json = AsyncMock(return_value={"ok": True})
        mock_fetch.return_value = mock_resp

        context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            global_context={"field": "file-token"},
        )

        _, status = await handler.process(context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        _, kwargs = mock_fetch.await_args
        self.assertNotIn("Content-Type", kwargs["headers"])
        self.assertIsInstance(kwargs["data"], aiohttp.FormData)
        self.assertIsNone(kwargs["json"])

    async def test_logic_node_evaluation(self):
        cfg = NodeConfig(
            id="logic",
            name="Logic",
            type=NodeType.LOGIC,
            config=LogicNodeConfig(
                condition="global_context.a > 5",
                true_next_node_id="T",
                false_next_node_id="F",
            ),
        )
        handler = LogicNodeHandler(cfg)

        ok_context = WorkflowExecutionContext(run_id=uuid.uuid4(), global_context={"a": 6})
        bad_context = WorkflowExecutionContext(run_id=uuid.uuid4(), global_context={"a": 5})

        ok_value, ok_status = await handler.process(ok_context)
        bad_value, bad_status = await handler.process(bad_context)

        self.assertEqual(ok_status, NodeStatus.SUCCESS)
        self.assertTrue(ok_value["result"])
        self.assertEqual(ok_value["selected_branch"], "TRUE")
        self.assertEqual(bad_status, NodeStatus.SUCCESS)
        self.assertFalse(bad_value["result"])
        self.assertEqual(bad_value["selected_branch"], "FALSE")

    async def test_loop_node_exit_condition_semantics(self):
        cfg = NodeConfig(
            id="loop",
            name="Loop",
            type=NodeType.LOOP,
            config=LoopNodeConfig(
                condition="context.loop_index >= 3",
                body_entry_id="body",
                exit_node_id="exit",
                max_iterations=5,
            ),
        )
        handler = LoopNodeHandler(cfg)

        continue_context = WorkflowExecutionContext(run_id=uuid.uuid4(), loop_index=1)
        exit_context = WorkflowExecutionContext(run_id=uuid.uuid4(), loop_index=3)

        continue_output, continue_status = await handler.process(continue_context)
        exit_output, exit_status = await handler.process(exit_context)

        self.assertEqual(continue_status, NodeStatus.SUCCESS)
        self.assertFalse(continue_output["exit_condition_met"])
        self.assertEqual(continue_output["decision"], "CONTINUE")

        self.assertEqual(exit_status, NodeStatus.SUCCESS)
        self.assertTrue(exit_output["exit_condition_met"])
        self.assertEqual(exit_output["decision"], "EXIT")

    async def test_loop_node_supports_runtime_dunder_context_access(self):
        cfg = NodeConfig(
            id="loop-runtime",
            name="Loop Runtime",
            type=NodeType.LOOP,
            config=LoopNodeConfig(
                condition="context.__runtime__.last_status != 'SUCCESS'",
                body_entry_id="body",
                exit_node_id="exit",
                max_iterations=5,
            ),
        )
        handler = LoopNodeHandler(cfg)

        continue_context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            loop_index=1,
            global_context={"__runtime__": {"last_status": "FAILURE"}},
        )
        exit_context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            loop_index=1,
            global_context={"__runtime__": {"last_status": "SUCCESS"}},
        )

        continue_output, continue_status = await handler.process(continue_context)
        exit_output, exit_status = await handler.process(exit_context)

        self.assertEqual(continue_status, NodeStatus.SUCCESS)
        self.assertTrue(continue_output["exit_condition_met"])
        self.assertEqual(exit_status, NodeStatus.SUCCESS)
        self.assertFalse(exit_output["exit_condition_met"])

    async def test_loop_node_defers_boundary_exit_for_loop_index_threshold(self):
        cfg = NodeConfig(
            id="loop-boundary",
            name="Loop Boundary",
            type=NodeType.LOOP,
            config=LoopNodeConfig(
                condition="context.loop_index >= 3",
                body_entry_id="body",
                exit_node_id="exit",
                max_iterations=3,
            ),
        )
        handler = LoopNodeHandler(cfg)

        boundary_context = WorkflowExecutionContext(run_id=uuid.uuid4(), loop_index=3)
        output, status = await handler.process(boundary_context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertFalse(output["exit_condition_met"])
        self.assertEqual(output["decision"], "CONTINUE")
        self.assertTrue(output["deferred_exit_by_max_boundary"])

    async def test_loop_node_keeps_boundary_exit_for_non_threshold_conditions(self):
        cfg = NodeConfig(
            id="loop-boundary-runtime",
            name="Loop Boundary Runtime",
            type=NodeType.LOOP,
            config=LoopNodeConfig(
                condition="context.__runtime__.last_status != 'SUCCESS'",
                body_entry_id="body",
                exit_node_id="exit",
                max_iterations=3,
            ),
        )
        handler = LoopNodeHandler(cfg)

        boundary_context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            loop_index=3,
            global_context={"__runtime__": {"last_status": "FAILURE"}},
        )
        output, status = await handler.process(boundary_context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertTrue(output["exit_condition_met"])
        self.assertEqual(output["decision"], "EXIT")
        self.assertFalse(output["deferred_exit_by_max_boundary"])

    async def test_transform_node(self):
        cfg = NodeConfig(
            id="trans",
            name="Transform",
            type=NodeType.TRANSFORM,
            config=TransformNodeConfig(
                output_schema={
                    "full_name": "{{ global_context.first }} {{ global_context.last }}",
                    "age": "{{ global_context.age_str }}",
                }
            ),
        )
        handler = TransformNodeHandler(cfg)

        context = WorkflowExecutionContext(
            run_id=uuid.uuid4(),
            global_context={"first": "John", "last": "Doe", "age_str": "30"},
        )
        output, status = await handler.process(context)

        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(output, {"full_name": "John Doe", "age": "30"})


if __name__ == "__main__":
    unittest.main()

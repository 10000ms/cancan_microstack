"""
工作流节点处理器
Workflow Node Handlers

此文件包含处理不同类型工作流节点的领域逻辑。
This file contains the domain logic for processing different types of workflow nodes.
"""
from typing import (
    Dict,
    Any,
    Optional,
    Tuple,
    Type,
)

import aiohttp
import jinja2
import jmespath
from pydantic import BaseModel

from cancan_microstack.public.schemas.infra.workflow import (
    NodeConfig,
    ActionNodeConfig,
    RequestConfig,
    LogicNodeConfig,
    TransformNodeConfig,
    ForkNodeConfig,
    JoinNodeConfig,
    LoopNodeConfig,
    EndNodeConfig,
    WorkflowExecutionContext,
    WorkflowDefinition,
    HttpResponseOutput,
)
from cancan_microstack.public.schemas.infra.enums import (
    NodeStatus,
    JoinMode,
    EndStatus,
    TransformEngine,
    ConditionTruth,
)
from linglong_web import http_client
from linglong_web.utils import logger


def _evaluate_truthy_flag(raw_value: str) -> bool:
    """将条件表达式渲染后的字符串转换为布尔值 / Convert rendered condition string into boolean."""

    normalized = (raw_value or "").strip().lower()
    try:
        truth = ConditionTruth(normalized)
    except ValueError:
        truth = ConditionTruth.FALSE if normalized in {"", "0"} else ConditionTruth.TRUE
    return truth is ConditionTruth.TRUE


class NodeHandler:
    """所有节点的基类处理器 / TableBase handler for all nodes."""

    def __init__(self, node_config: NodeConfig):
        self.node_config = node_config

    def _ensure_config_model(self, model_cls: Type[BaseModel]) -> Any:
        """
        确保节点配置被解析为期望的 Pydantic 模型
        Ensure the node config is parsed into the expected Pydantic model
        """

        config = self.node_config.config
        if config is None or isinstance(config, model_cls):
            return config
        if isinstance(config, dict):
            try:
                typed_config = model_cls.model_validate(config)
                self.node_config.config = typed_config
                return typed_config
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to coerce config for node %s into %s: %s",
                    self.node_config.id,
                    model_cls.__name__,
                    exc,
                )
        return config

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Any, NodeStatus]:
        """
        处理节点的核心方法。
        Core method for processing the node.
        """
        raise NotImplementedError

    @staticmethod
    def _build_template_context(context: WorkflowExecutionContext) -> Dict[str, Any]:
        """构建模板上下文，支持工作流官方模板写法。
        Build template context for official workflow template syntax.

        约定（官方）/ Official conventions:
        - `context.xxx` 访问执行上下文顶层字段
        - `context.global_context.xxx` 访问业务上下文
        - `context.__runtime__.xxx` 访问运行时命名空间
        """

        payload = context.model_dump()
        global_context = payload.get("global_context")
        runtime_context: Dict[str, Any] = {}
        if isinstance(global_context, dict):
            runtime_context = dict(global_context.get("__runtime__") or {})
            global_context.setdefault("__runtime__", runtime_context)
            for key, value in global_context.items():
                if key not in payload:
                    payload[key] = value
        payload["runtime"] = runtime_context
        payload["context"] = payload
        return payload

    @staticmethod
    def _prepare_template_expression(template_expr: str) -> str:
        """将官方 runtime 点语法转换为 Jinja 可解析形式。
        Convert official runtime dot syntax into Jinja-parseable form.

        官方写法 / Official syntax:
        - `context.__runtime__.last_status`

        Jinja 对双下划线键的点访问会触发属性解析限制，
        因此仅对 `context.__runtime__` 做确定性转换。
        """

        normalized = template_expr
        normalized = normalized.replace("context.__runtime__", "context['__runtime__']")
        return normalized


class StartNodeHandler(NodeHandler):
    """处理开始节点 / Handles Start Nodes."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        return {
            "run_id": str(context.run_id),
            "loop_index": context.loop_index,
            "message": "START node accepted trigger context",
        }, NodeStatus.SUCCESS


class ActionNodeHandler(NodeHandler):
    """处理动作节点，负责执行 HTTP 请求 / Handles Action Nodes for HTTP requests."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[HttpResponseOutput, NodeStatus]:
        config = self._ensure_config_model(ActionNodeConfig)
        if not isinstance(config, ActionNodeConfig):
            raise ValueError("Invalid action node config")
        req_conf = config.request
        env = jinja2.Environment()

        input_dict = self._build_template_context(context)
        rendered_url = env.from_string(req_conf.url).render(**input_dict)
        rendered_headers = {k: env.from_string(v).render(**input_dict) for k, v in (req_conf.headers or {}).items()}
        rendered_params = {k: env.from_string(v).render(**input_dict) for k, v in (req_conf.params or {}).items()}

        json_payload, data_payload = self._resolve_request_body(req_conf, rendered_headers, env, input_dict)

        if config.async_mode and context.callback_url:
            rendered_headers["X-Callback-Url"] = context.callback_url

        resp = await http_client.fetch(
            method=req_conf.method,
            url=rendered_url,
            params=rendered_params,
            headers=rendered_headers,
            json=json_payload,
            data=data_payload,
            timeout=req_conf.timeout_seconds,
            passthrough_errors=True
        )

        text_content = await resp.text()
        json_content = None
        if "application/json" in resp.headers.get("Content-Type", ""):
            try:
                json_content = await resp.json(content_type=None)
            except Exception:
                logger.warning(f"Failed to decode JSON from response: {rendered_url}")

        output = HttpResponseOutput(
            status_code=resp.status,
            headers=dict(resp.headers),
            text=text_content,
            json_body=json_content,
            ok=resp.ok,
        )
        status = NodeStatus.SUSPENDED if config.async_mode else NodeStatus.SUCCESS
        return output, status

    def _resolve_request_body(
            self,
            req_conf: RequestConfig,
            headers: Dict[str, str],
            env: jinja2.Environment,
            context: Dict[str, Any],
    ) -> Tuple[Optional[Any], Optional[Any]]:
        """解析请求体并自动适配 json/data 及 Content-Type。"""

        rendered_legacy_body = self._render_recursive(req_conf.body, env, context)
        rendered_json_body = self._render_recursive(req_conf.json_body, env, context)
        rendered_form_body = self._render_recursive(req_conf.form_body, env, context)
        rendered_raw_body = self._render_recursive(req_conf.raw_body, env, context)

        content_type = ""
        for key, value in headers.items():
            if key.lower() == "content-type":
                content_type = str(value).lower()
                break

        body_type = req_conf.body_type
        if body_type == "auto":
            if rendered_json_body is not None:
                body_type = "json"
            elif rendered_form_body is not None:
                if "multipart/form-data" in content_type:
                    body_type = "multipart"
                else:
                    body_type = "form-urlencoded"
            elif rendered_raw_body is not None:
                body_type = "raw"
            else:
                if "multipart/form-data" in content_type:
                    body_type = "multipart"
                elif "application/x-www-form-urlencoded" in content_type:
                    body_type = "form-urlencoded"
                elif isinstance(rendered_legacy_body, (dict, list)):
                    body_type = "json"
                else:
                    body_type = "raw"

        if body_type == "json":
            json_payload = rendered_json_body if rendered_json_body is not None else rendered_legacy_body
            if json_payload is not None and not content_type:
                headers["Content-Type"] = "application/json"
            return json_payload, None

        if body_type == "form-urlencoded":
            form_payload = rendered_form_body if rendered_form_body is not None else rendered_legacy_body
            if form_payload is not None and not content_type:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            return None, form_payload

        if body_type == "multipart":
            multipart_payload = rendered_form_body if rendered_form_body is not None else rendered_legacy_body
            normalized = self._to_form_data(multipart_payload)

            content_type_keys = [key for key in headers if key.lower() == "content-type"]
            for key in content_type_keys:
                headers.pop(key, None)
            return None, normalized

        raw_payload = rendered_raw_body if rendered_raw_body is not None else rendered_legacy_body
        return None, raw_payload

    @staticmethod
    def _to_form_data(payload: Any) -> aiohttp.FormData:
        """将 payload 规范化为 multipart FormData。"""

        form = aiohttp.FormData()
        if isinstance(payload, dict):
            for key, value in payload.items():
                form.add_field(str(key), "" if value is None else str(value))
            return form

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    key, value = item
                    form.add_field(str(key), "" if value is None else str(value))
            return form

        if payload is not None:
            form.add_field("payload", str(payload))
        return form

    def _render_recursive(self, data: Any, env: jinja2.Environment, context: Dict[str, Any]) -> Any:
        if isinstance(data, str):
            normalized = self._prepare_template_expression(data)
            return env.from_string(normalized).render(**context)
        elif isinstance(data, dict):
            return {k: self._render_recursive(v, env, context) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._render_recursive(v, env, context) for v in data]
        return data


class LogicNodeHandler(NodeHandler):
    """处理逻辑节点，用于评估条件表达式 / Handles Logic Nodes for conditions."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        config = self._ensure_config_model(LogicNodeConfig)
        if not isinstance(config, LogicNodeConfig):
            raise ValueError("Invalid logic node config")
        env = jinja2.Environment()
        expr = config.condition
        if not expr.startswith("{{"):
            expr = f"{{{{ {expr} }}}}"
        expr = self._prepare_template_expression(expr)

        rendered = env.from_string(expr).render(**self._build_template_context(context))
        result = _evaluate_truthy_flag(rendered)
        return {
            "condition": config.condition,
            "rendered": rendered,
            "result": result,
            "selected_branch": "TRUE" if result else "FALSE",
            "true_next_node_id": config.true_next_node_id,
            "false_next_node_id": config.false_next_node_id,
        }, NodeStatus.SUCCESS


class TransformNodeHandler(NodeHandler):
    """处理转换节点，用于重塑上下文数据 / Handles Transform Nodes for reshaping data."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        config = self._ensure_config_model(TransformNodeConfig)
        if not isinstance(config, TransformNodeConfig):
            raise ValueError("Invalid transform node config")
        result = {}
        input_dict = self._build_template_context(context)

        for tgt_key, expr in config.output_schema.items():
            try:
                if config.engine == TransformEngine.JMESPATH:
                    val = jmespath.search(expr, input_dict)
                    result[tgt_key] = val
                else:
                    template = jinja2.Template(self._prepare_template_expression(expr))
                    val = template.render(**input_dict)
                    result[tgt_key] = val
            except Exception as e:
                logger.error(f"Failed to transform key '{tgt_key}' with expression '{expr}': {e}")
                result[tgt_key] = None
        return result, NodeStatus.SUCCESS


class ForkNodeHandler(NodeHandler):
    """处理并行分支节点 / Handles Fork Nodes for parallel execution."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        config = self._ensure_config_model(ForkNodeConfig)
        if not isinstance(config, ForkNodeConfig):
            raise ValueError("Invalid fork node config")
        """
        处理并行分支节点，直接返回成功状态。
        Process fork node and return success status directly.
        
        并行逻辑由 WorkflowEngine._determine_next_nodes 实现，
        该方法会将 config.branch_node_ids 返回为 next_node_ids，
        Celery 任务编排层会为每个分支创建独立的执行任务。
        
        The parallel logic is implemented by WorkflowEngine._determine_next_nodes,
        which returns config.branch_node_ids as next_node_ids.
        The Celery orchestration layer will create independent execution tasks for each branch.
        """
        # Fork 节点本身不执行任何操作，只是语义标记
        # Fork node itself performs no operation, it's just a semantic marker
        return {
            "branch_node_ids": config.branch_node_ids,
            "branch_count": len(config.branch_node_ids or []),
        }, NodeStatus.SUCCESS


class JoinNodeHandler(NodeHandler):
    """处理汇合节点 / Handles Join Nodes."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        workflow_def: WorkflowDefinition = kwargs.get("workflow_def")
        if not workflow_def:
            raise ValueError("workflow_def is required for JoinNodeHandler")

        join_config = self._ensure_config_model(JoinNodeConfig)
        if not isinstance(join_config, JoinNodeConfig):
            raise ValueError("Invalid join node config")

        upstream_node_ids = [
            nid for nid, n_cfg_dict in workflow_def.nodes_config.items()
            if self.node_config.id in (n_cfg_dict.get('next_node_ids') or [])
        ]

        if not upstream_node_ids:
            return {
                "mode": join_config.mode.value,
                "upstream_node_ids": [],
                "upstream_statuses": {},
                "is_ready": True,
                "reason": "No upstream nodes found",
            }, NodeStatus.SUCCESS

        upstream_status_map = {
            uid: (context.nodes.get(uid).status.value if context.nodes.get(uid) else "MISSING")
            for uid in upstream_node_ids
        }
        upstream_statuses = [context.nodes.get(uid).status for uid in upstream_node_ids if context.nodes.get(uid)]

        if join_config.mode == JoinMode.ALL:
            is_ready = all(s in [NodeStatus.SUCCESS, NodeStatus.SKIPPED] for s in upstream_statuses)
        else:
            is_ready = any(s == NodeStatus.SUCCESS for s in upstream_statuses)

        return {
            "mode": join_config.mode.value,
            "upstream_node_ids": upstream_node_ids,
            "upstream_statuses": upstream_status_map,
            "is_ready": is_ready,
        }, NodeStatus.SUCCESS if is_ready else NodeStatus.PENDING


class LoopNodeHandler(NodeHandler):
    """处理循环节点 / Handles Loop Nodes."""

    def _evaluate_exit_condition(
            self,
            config: LoopNodeConfig,
            context: WorkflowExecutionContext,
            loop_index_override: Optional[int] = None,
    ) -> Tuple[str, bool]:
        """渲染并评估循环退出条件。
        Render and evaluate loop exit condition.

        Args:
            config: 循环配置 / Loop config.
            context: 当前执行上下文 / Current execution context.
            loop_index_override: 可选覆盖 loop_index（用于边界轮次对比）/
                Optional override of loop_index (used for boundary comparison).
        """

        env = jinja2.Environment()
        expr = config.condition
        if not expr.startswith("{{"):
            expr = f"{{{{ {expr} }}}}"
        expr = self._prepare_template_expression(expr)

        template_context = self._build_template_context(context)
        if loop_index_override is not None:
            template_context["loop_index"] = loop_index_override
            nested_context = template_context.get("context")
            if isinstance(nested_context, dict):
                nested_context["loop_index"] = loop_index_override

        rendered = env.from_string(expr).render(**template_context)
        return rendered, _evaluate_truthy_flag(rendered)

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        config = self._ensure_config_model(LoopNodeConfig)
        if not isinstance(config, LoopNodeConfig):
            raise ValueError("Invalid loop node config")

        if context.loop_index > config.max_iterations:
            return {
                "condition": config.condition,
                "rendered": None,
                "exit_condition_met": True,
                "decision": "EXIT",
                "forced_exit_by_max_iterations": True,
                "max_iterations": config.max_iterations,
                "current_loop_index": context.loop_index,
            }, NodeStatus.SUCCESS

        rendered, exit_condition_met = self._evaluate_exit_condition(config, context)

        # 边界轮次防误判：当条件仅在 loop_index == max_iterations 才变为 true 时，
        # 应允许本轮循环体执行，避免出现“max=3 但 body 仅 2 次”的 off-by-one。
        # Boundary guard: when condition flips true only at loop_index == max_iterations,
        # allow current body execution to avoid off-by-one (max=3 but body runs only twice).
        deferred_by_boundary = False
        boundary_probe_rendered = None
        if exit_condition_met and context.loop_index == config.max_iterations:
            boundary_probe_rendered, previous_iteration_exit = self._evaluate_exit_condition(
                config,
                context,
                loop_index_override=max(context.loop_index - 1, 0),
            )
            if not previous_iteration_exit:
                deferred_by_boundary = True
                exit_condition_met = False

        return {
            "condition": config.condition,
            "rendered": rendered,
            "boundary_probe_rendered": boundary_probe_rendered,
            "exit_condition_met": exit_condition_met,
            "decision": "EXIT" if exit_condition_met else "CONTINUE",
            "deferred_exit_by_max_boundary": deferred_by_boundary,
            "forced_exit_by_max_iterations": False,
            "max_iterations": config.max_iterations,
            "current_loop_index": context.loop_index,
        }, NodeStatus.SUCCESS


class EndNodeHandler(NodeHandler):
    """处理结束节点 / Handles End Nodes."""

    async def process(self, context: WorkflowExecutionContext, **kwargs) -> Tuple[Dict[str, Any], NodeStatus]:
        config = self._ensure_config_model(EndNodeConfig)
        if config is None:
            config = EndNodeConfig()
            self.node_config.config = config
        if not isinstance(config, EndNodeConfig):
            raise ValueError("Invalid end node config")
        status = NodeStatus.SUCCESS if config.status == EndStatus.SUCCESS else NodeStatus.FAILURE
        return {
            "end_status": config.status.value,
            "loop_index": context.loop_index,
        }, status

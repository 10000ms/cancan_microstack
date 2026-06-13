"""
工作流执行引擎领域服务
Workflow Execution Engine Domain Service
"""
from typing import (
    Any,
    List,
    Tuple,
)

from cancan_microstack.public.schemas.infra.enums import (
    NodeStatus,
    NodeType,
)
from cancan_microstack.public.schemas.infra.workflow import (
    NodeConfig,
    WorkflowExecutionContext,
    WorkflowDefinition,
    LogicNodeConfig,
    ForkNodeConfig,
    LoopNodeConfig,
)
from .node_handlers import (
    StartNodeHandler,
    ActionNodeHandler,
    TransformNodeHandler,
    LogicNodeHandler,
    ForkNodeHandler,
    JoinNodeHandler,
    LoopNodeHandler,
    EndNodeHandler,
)
from linglong_web.utils import logger


class WorkflowEngine:
    """
    工作流引擎，负责编排和执行节点逻辑。
    The workflow engine, responsible for orchestrating and executing node logic.
    """

    def __init__(self):
        # 注册可用的节点处理器，便于根据类型动态分发
        # Register available node handlers so we can dispatch by type at runtime
        self._handlers = {
            NodeType.START: StartNodeHandler,
            NodeType.ACTION: ActionNodeHandler,
            NodeType.TRANSFORM: TransformNodeHandler,
            NodeType.LOGIC: LogicNodeHandler,
            NodeType.FORK: ForkNodeHandler,
            NodeType.JOIN: JoinNodeHandler,
            NodeType.LOOP: LoopNodeHandler,
            NodeType.END: EndNodeHandler,
        }

    async def process_node(
            self,
            workflow_def: WorkflowDefinition,
            node_config: NodeConfig,
            context: WorkflowExecutionContext,
    ) -> Tuple[Any, NodeStatus, List[str], int]:
        """
        处理单个节点并返回结果、状态、下一个节点ID和新的循环索引。
        Process a single node and return the result, status, next node IDs, and new loop index.
        """
        # 1. 通过节点类型选择处理器 / Lookup handler class by node type
        handler_class = self._handlers.get(node_config.type)
        if not handler_class:
            logger.warning(f"No handler found for node type: {node_config.type}")
            return None, NodeStatus.FAILURE, [], context.loop_index

        handler = handler_class(node_config)

        # 2. 特定处理器需要额外依赖 / Some handlers (e.g., JOIN) require extra dependencies
        if node_config.type == NodeType.JOIN:
            output, status = await handler.process(context, workflow_def=workflow_def)
        else:
            output, status = await handler.process(context)

        # 3. 根据节点输出决定后续节点与循环索引 / Compute downstream topology and loop index
        next_node_ids, new_loop_index = self._determine_next_nodes(
            node_config, output, context.loop_index
        )

        return output, status, next_node_ids, new_loop_index

    def _determine_next_nodes(
            self, node_config: NodeConfig, output: Any, current_loop_index: int
    ) -> Tuple[List[str], int]:
        """
        根据节点结果确定下一个节点和循环索引。
        Determine next nodes and loop index based on node result.
        """
        next_ids = []
        new_loop_index = current_loop_index

        if node_config.type == NodeType.LOGIC:
            config: LogicNodeConfig = node_config.config
            condition_result = False
            if isinstance(output, dict):
                condition_result = bool(output.get("result"))
            else:
                condition_result = bool(output)

            target = config.true_next_node_id if condition_result else config.false_next_node_id
            if target:
                next_ids.append(target)
        elif node_config.type == NodeType.FORK:
            # 并行分支节点：返回所有分支节点 ID
            # Fork node: return all branch node IDs for parallel execution
            config: ForkNodeConfig = node_config.config
            if config.branch_node_ids:
                next_ids.extend(config.branch_node_ids)
        elif node_config.type == NodeType.LOOP:
            config: LoopNodeConfig = node_config.config
            body_entry_id = config.body_entry_id or config.jump_target_id
            exit_candidates = []
            if config.exit_node_id:
                exit_candidates.append(config.exit_node_id)
            elif node_config.next_node_ids:
                exit_candidates.extend(node_config.next_node_ids)

            should_exit = False
            if isinstance(output, dict):
                should_exit = bool(output.get("exit_condition_met"))
            else:
                should_exit = bool(output)

            if not should_exit:
                if body_entry_id:
                    next_ids.append(body_entry_id)
                else:
                    # 缺少循环体配置时记录警告并走退出路径
                    # Warn and fallback to exit path when loop body is missing
                    logger.warning(
                        "Loop node %s lacks body_entry_id, falling back to exit path",
                        node_config.id,
                    )
                    next_ids.extend(exit_candidates)
            else:
                next_ids.extend(exit_candidates)
        else:
            if node_config.next_node_ids:
                next_ids.extend(node_config.next_node_ids)

        # 去重以避免重复派发，但保持结果顺序稳定
        # Deduplicate next nodes to avoid double dispatch while keeping ordering stable
        seen = set()
        ordered_next_ids = []
        for nid in next_ids:
            if nid and nid not in seen:
                seen.add(nid)
                ordered_next_ids.append(nid)

        return ordered_next_ids, new_loop_index


# Singleton instance
workflow_engine = WorkflowEngine()

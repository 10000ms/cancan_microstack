"""
工作流运维应用层（opsbffsrv）
Workflow Operations Application Layer (opsbffsrv)

职责 / Responsibilities:
1. 调用 infrasrv API / Call infrasrv APIs
2. 数据转换和格式化 / Data transformation and formatting
3. 错误处理和日志记录 / Error handling and logging
"""
from typing import (
    Optional,
    List,
    Dict,
    Any,
)

from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.schemas.infra import workflow as wt
from cancan_microstack.public.api.infrasrv_client import InfraSrvApiClient
from cancan_microstack.public.const.workflow_consts import (
    IMMUTABLE_END_NODE_IDS,
    IMMUTABLE_START_NODE_IDS,
)
from linglong_web import LinglongConfig
from linglong_web.utils import logger


class WorkflowOpsApp:
    """工作流运维应用服务 / Workflow operations application service"""

    def __init__(self):
        self.infra_client = InfraSrvApiClient(LinglongConfig.INFRASRV_HOST)

    async def list_workflows(self, query: wt.WorkflowListQuery) -> wt.WorkflowListResponse:
        """
        列出工作流定义（支持分页和过滤）
        List workflow definitions (with pagination and filtering)

        Args:
            query: 查询参数 / Query parameters

        Returns:
            工作流列表响应 / Workflow list response
        """
        try:
            # 调用 infrasrv 接口 / Call infrasrv API
            response = await self.infra_client.list_workflow_definitions(
                page=query.page,
                page_size=query.page_size,
                keyword=query.keyword,
                status=query.status,
            )

            if not response.success:
                logger.error(f"Failed to list workflows from infrasrv: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

            raw_payload = response.data
            if isinstance(raw_payload, wt.WorkflowListResponse):
                payload = raw_payload
            else:
                payload_dict = raw_payload or {}
                payload = wt.WorkflowListResponse(**payload_dict) if payload_dict else wt.WorkflowListResponse(
                    list=[],
                    total=0,
                    page=query.page,
                    page_size=query.page_size,
                )
            workflows = payload.list
            total = payload.total
            filtered_workflows = workflows
            filters_applied = False

            # 过滤逻辑（infrasrv 暂不支持，opsbffsrv 层处理）
            # Filtering logic (infrasrv doesn't support yet, handle in opsbffsrv)
            if query.keyword:
                filters_applied = True
                keyword_lower = query.keyword.lower()
                filtered_workflows = [
                    workflow for workflow in filtered_workflows
                    if self._workflow_matches_keyword(workflow, keyword_lower)
                ]

            if query.status:
                filters_applied = True
                is_active = query.status == "ACTIVE"
                filtered_workflows = [
                    workflow for workflow in filtered_workflows
                    if workflow.is_active == is_active
                ]

            final_total = len(filtered_workflows) if filters_applied else total

            return wt.WorkflowListResponse(
                list=filtered_workflows,
                total=final_total,
                page=query.page,
                page_size=query.page_size
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing workflows: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def get_workflow(self, workflow_id: str) -> wt.WorkflowDefinition:
        """
        获取工作流详情
        Get workflow details

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier

        Returns:
            工作流详情 / Workflow details
        """
        try:
            response = await self.infra_client.get_workflow_definition(workflow_id)

            if not response.success:
                logger.error(f"Failed to get workflow {workflow_id} from infrasrv: {response.error}")
                upstream_code = str(response.error.code) if response.error and response.error.code else ""
                if upstream_code == "404":
                    raise HTTPException(status_code=404, msg="Workflow not found")
                raise HTTPException(
                    status_code=500,
                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}",
                )

            return self._parse_workflow_definition(response.data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def list_workflow_versions(self, workflow_id: str, limit: int = 50) -> wt.WorkflowVersionListResponse:
        """列出工作流版本历史
        List workflow definition versions for UI consumption"""

        try:
            response = await self.infra_client.list_workflow_versions(workflow_id, limit)

            if not response.success:
                logger.error(f"Failed to list workflow versions for {workflow_id}: {response.error}")
                raise HTTPException(status_code=500, msg="Failed to fetch workflow versions")

            payload = response.data or {}
            if isinstance(payload, wt.WorkflowVersionListResponse):
                return payload
            return wt.WorkflowVersionListResponse(**payload)

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error listing workflow versions for {workflow_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def create_workflow(self, payload: wt.WorkflowDefinitionCreate) -> wt.WorkflowDefinition:
        """
        创建工作流
        Create workflow

        Args:
            payload: 工作流定义数据 / Workflow definition data

        Returns:
            已创建的工作流 / Created workflow
        """
        try:
            response = await self.infra_client.create_workflow_definition(payload.model_dump())

            if not response.success:
                logger.error(f"Failed to create workflow: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

            return self._parse_workflow_definition(response.data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating workflow: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def update_workflow(self, workflow_id: str, payload: wt.WorkflowDefinitionUpdate) -> wt.WorkflowDefinition:
        """
        更新工作流
        Update workflow

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier
            payload: 更新数据 / Update data

        Returns:
            更新后的工作流 / Updated workflow
        """
        try:
            response = await self.infra_client.update_workflow_definition(workflow_id,
                                                                          payload.model_dump(exclude_unset=True))

            if not response.success:
                logger.error(f"Failed to update workflow {workflow_id}: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

            return self._parse_workflow_definition(response.data)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def delete_workflow(self, workflow_id: str) -> None:
        """
        删除工作流
        Delete workflow

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier
        """
        try:
            response = await self.infra_client.delete_workflow_definition(workflow_id)

            if not response.success:
                logger.error(f"Failed to delete workflow {workflow_id}: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def toggle_workflow(self, workflow_id: str) -> wt.WorkflowDefinition:
        """
        切换工作流启用状态
        Toggle workflow active status

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier

        Returns:
            更新后的工作流 / Updated workflow
        """
        try:
            # 先获取当前状态 / Get current status first
            workflow = await self.get_workflow(workflow_id)

            # 更新状态 / Update status
            payload = wt.WorkflowDefinitionUpdate(is_active=not workflow.is_active)
            return await self.update_workflow(workflow_id, payload)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error toggling workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def duplicate_workflow(self, workflow_id: str, payload: wt.DuplicateWorkflowPayload) -> wt.WorkflowDefinition:
        """
        复制工作流
        Duplicate workflow

        Args:
            workflow_id: 源工作流唯一标识符 / Source workflow unique identifier
            payload: 复制配置 / Duplication config

        Returns:
            复制后的工作流 / Duplicated workflow
        """
        try:
            # 获取源工作流 / Get source workflow
            source = await self.get_workflow(workflow_id)

            # 创建副本 / Create copy
            create_payload = wt.WorkflowDefinitionCreate(
                name=payload.name,
                description=f"Copy of {source.name}",
                schedule=source.schedule,
                graph_data=source.graph_data,
                nodes_config=source.nodes_config,
                global_context=source.global_context,
                is_active=False  # 副本默认禁用 / Copy is inactive by default
            )

            return await self.create_workflow(create_payload)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error duplicating workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def publish_workflow(self, workflow_id: str) -> wt.WorkflowDefinition:
        """
        发布工作流（标记为生产就绪）
        Publish workflow (mark as production-ready)

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier

        Returns:
            发布后的工作流 / Published workflow
        """
        try:
            # 发布即启用 / Publish means activate
            payload = wt.WorkflowDefinitionUpdate(is_active=True)
            return await self.update_workflow(workflow_id, payload)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error publishing workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def rollback_workflow(self, workflow_id: str, payload: wt.WorkflowRollbackRequest) -> wt.WorkflowDefinition:
        """回滚工作流定义
        Roll back workflow definition to a target version"""

        try:
            response = await self.infra_client.rollback_workflow_definition(
                workflow_id,
                payload.model_dump(exclude_none=True),
            )

            if not response.success:
                logger.error(f"Failed to rollback workflow {workflow_id}: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

            return self._parse_workflow_definition(response.data)

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error rolling back workflow {workflow_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    @staticmethod
    def _workflow_matches_keyword(workflow: wt.WorkflowDefinition, keyword_lower: str) -> bool:
        """匹配关键字 / Check if workflow matches keyword"""

        searchable_fields = [
            (workflow.name or "").lower(),
            (workflow.description or "").lower(),
        ]

        global_ctx = workflow.global_context or {}
        tags_value = global_ctx.get("tags")
        if isinstance(tags_value, list):
            searchable_fields.extend(str(tag).lower() for tag in tags_value)

        return any(keyword_lower in field for field in searchable_fields if field)

    @staticmethod
    def _parse_workflow_definition(data: Any) -> wt.WorkflowDefinition:
        """
        解析工作流定义响应，兼容字典与模型
        Normalize workflow definition payload returned from infrasrv
        """

        if isinstance(data, wt.WorkflowDefinition):
            return data
        if isinstance(data, dict):
            return wt.WorkflowDefinition(**data)
        raise HTTPException(status_code=500, msg="Invalid workflow payload from infrasrv")

    @staticmethod
    def _normalize_nodes_config(nodes_config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """统一节点配置格式，兼容 Pydantic 模型与原始字典
        Normalize node configuration values (dict or Pydantic models) into plain dicts"""

        normalized: Dict[str, Dict[str, Any]] = {}
        if not nodes_config:
            return normalized

        for node_id, node in nodes_config.items():
            normalized[node_id] = WorkflowOpsApp._normalize_single_node(node)
        return normalized

    @staticmethod
    def _normalize_single_node(node: Any) -> Dict[str, Any]:
        """转换单个节点配置为标准 dict 格式，便于统一校验
        Convert an individual node config into a dict for downstream validation"""

        if isinstance(node, wt.NodeConfig):
            payload = node.model_dump()
        elif hasattr(node, "model_dump"):
            payload = node.model_dump()
        elif isinstance(node, dict):
            payload = dict(node)
        else:
            raise HTTPException(status_code=500, msg="Invalid node configuration payload")

        node_type = payload.get("type")
        payload["type"] = str(node_type).upper() if node_type is not None else None

        raw_next_ids = payload.get("next_node_ids")
        next_ids: List[str] = []
        if isinstance(raw_next_ids, list):
            next_ids = [str(item) for item in raw_next_ids if item is not None]

        single_next = payload.get("next_node_id")
        if single_next:
            candidate = str(single_next)
            if candidate not in next_ids:
                next_ids.append(candidate)

        payload["next_node_ids"] = next_ids
        return payload

    async def validate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        验证工作流定义
        Validate workflow definition

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier

        Returns:
            验证结果 / Validation result
        """
        try:
            workflow = await self.get_workflow(workflow_id)
            nodes_config = self._normalize_nodes_config(workflow.nodes_config)

            issues = []

            # 基础验证 / Basic validation
            if not workflow.name or not workflow.name.strip():
                issues.append("Workflow name cannot be empty")

            if not nodes_config:
                issues.append("Workflow must have at least one node")

            # 检查是否有 START 节点 / Check for START node
            start_nodes = [node for node in nodes_config.values() if node.get("type") == "START"]
            if not start_nodes:
                issues.append("Workflow must have a START node")
            elif len(start_nodes) > 1:
                issues.append("Workflow can only contain one START node")
            else:
                start_id = (start_nodes[0].get("id") or start_nodes[0].get("node_id") or "").lower()
                if start_id not in IMMUTABLE_START_NODE_IDS:
                    issues.append("START node id must remain immutable (start/start_node)")
                if not start_nodes[0].get("next_node_ids"):
                    issues.append("START node must define downstream nodes")

            # 检查是否有 END 节点 / Check for END node
            end_nodes = [node for node in nodes_config.values() if node.get("type") == "END"]
            if not end_nodes:
                issues.append("Workflow must have at least one END node")
            elif len(end_nodes) > 1:
                issues.append("Workflow can only contain one END node")
            else:
                end_id = (end_nodes[0].get("id") or end_nodes[0].get("node_id") or "").lower()
                if end_id not in IMMUTABLE_END_NODE_IDS:
                    issues.append("END node id must remain immutable (end/end_node)")

            # 检查节点连接 / Check node connections
            for node_id, node in nodes_config.items():
                next_ids = node.get("next_node_ids", [])
                for next_id in next_ids:
                    if next_id not in nodes_config:
                        issues.append(f"Node {node_id} references non-existent node {next_id}")

            return {
                "valid": len(issues) == 0,
                "issues": issues
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def get_workflow_stats(self) -> wt.WorkflowStats:
        """
        获取工作流统计
        Get workflow statistics

        Returns:
            统计信息 / Statistics
        """
        try:
            response = await self.infra_client.get_workflow_stats()

            if not response.success:
                logger.error(f"Failed to get workflow stats from infrasrv: {response.error}")
                # 降级：返回空统计 / Fallback: return empty stats
                return wt.WorkflowStats()

            payload = response.data
            if isinstance(payload, wt.WorkflowStats):
                return payload
            if isinstance(payload, dict):
                return wt.WorkflowStats(**payload)
            logger.warning("Unexpected workflow stats payload type: %s", type(payload))
            return wt.WorkflowStats()

        except Exception as e:
            logger.error(f"Error getting workflow stats: {e}", exc_info=True)
            # 降级：返回空统计 / Fallback: return empty stats
            return wt.WorkflowStats()

    async def trigger_workflow(
            self,
            workflow_id: str,
            payload: wt.WorkflowTriggerRequest,
    ) -> wt.WorkflowTriggerResponse:
        """
        触发工作流运行
        Trigger workflow run

        Args:
            workflow_id: 工作流唯一标识符 / Workflow unique identifier
            payload: 触发上下文数据 / Trigger context data

        Returns:
            运行实例信息 / Run instance info
        """
        try:
            response = await self.infra_client.trigger_workflow_run(workflow_id, payload.model_dump())

            if not response.success:
                logger.error(f"Failed to trigger workflow {workflow_id}: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

            payload = response.data
            if isinstance(payload, wt.WorkflowTriggerResponse):
                return payload
            if isinstance(payload, dict):
                return wt.WorkflowTriggerResponse(**payload)
            raise HTTPException(status_code=500, msg="Invalid trigger response payload")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error triggering workflow {workflow_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def list_runs(
            self,
            workflow_id: Optional[str],
            reqid: Optional[str],
            page: int,
            page_size: int,
            status: Optional[str] = None,
            date_from: Optional[str] = None,
            date_to: Optional[str] = None,
    ) -> wt.WorkflowRunListResponse:
        """
        列出工作流运行实例
        List workflow runs

        Args:
            workflow_id: 按工作流ID过滤 / Filter by workflow ID
            reqid: 按请求追踪 ID 过滤 / Filter by request trace ID
            page: 页码 / Page number
            page_size: 每页大小 / Page size

        Returns:
            运行实例列表 / Run instance list
        """
        try:
            response = await self.infra_client.list_workflow_runs(
                workflow_id=workflow_id,
                reqid=reqid,
                page=page,
                page_size=page_size,
                status=status,
                date_from=date_from,
                date_to=date_to,
            )

            if not response.success:
                logger.error(f"Failed to list workflow runs from infrasrv: {response.error}")
                raise HTTPException(status_code=500,
                                    msg=f"Upstream error: {response.error.msg if response.error else 'Unknown error'}")

            payload_dict = response.data or {}
            if not payload_dict:
                return wt.WorkflowRunListResponse(list=[], total=0, page=page, page_size=page_size)
            return wt.WorkflowRunListResponse(**payload_dict)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing workflow runs: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def get_run_graph_status(self, run_id: str) -> wt.RunGraphResponse:
        """
        获取运行图状态
        Get run graph status

        Args:
            run_id: 运行实例唯一标识符 / Run instance unique identifier

        Returns:
            图状态数据 / Graph status data
        """
        try:
            response = await self.infra_client.get_run_graph_status(run_id)

            if not response.success:
                logger.error(f"Failed to get run graph status for {run_id}: {response.error}")
                error_code = str(response.error.code) if response.error else "500"
                error_msg = response.error.msg if response.error else "Failed to fetch run graph"
                status_code = 404 if error_code == "404" else 500
                raise HTTPException(status_code=status_code, msg=error_msg or "Failed to fetch run graph")

            return wt.RunGraphResponse(**(response.data or {}))

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting run graph status for {run_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def get_node_history(self, run_id: str, node_id: str) -> wt.NodeExecutionHistoryResponse:
        """
        获取节点执行历史
        Get node execution history

        Args:
            run_id: 运行实例唯一标识符 / Run instance unique identifier
            node_id: 节点ID / Node ID

        Returns:
            节点执行历史 / Node execution history
        """
        try:
            response = await self.infra_client.get_node_history(run_id, node_id)

            if not response.success:
                logger.error(f"Failed to get node history for {run_id}/{node_id}: {response.error}")
                raise HTTPException(status_code=404, msg="Node history not found")

            payload = response.data or {}
            if not payload:
                return wt.NodeExecutionHistoryResponse(histories=[])
            return wt.NodeExecutionHistoryResponse(**payload)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting node history for {run_id}/{node_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def list_engine_alerts(self, query: wt.WorkflowEngineAlertQuery) -> wt.WorkflowEngineAlertListResponse:
        """列出工作流引擎告警 / List workflow engine alerts"""

        try:
            response = await self.infra_client.list_workflow_engine_alerts(
                status=query.status.value if query.status else None,
                severity=query.severity.value if query.severity else None,
                run_id=query.run_id,
                page=query.page,
                page_size=query.page_size,
            )
            if not response.success:
                logger.error(f"Failed to list workflow alerts: {response.error}")
                raise HTTPException(status_code=500, msg="Failed to fetch workflow alerts")

            payload = response.data or {}
            if isinstance(payload, wt.WorkflowEngineAlertListResponse):
                return payload
            if isinstance(payload, dict):
                return wt.WorkflowEngineAlertListResponse(**payload)
            return wt.WorkflowEngineAlertListResponse()
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error listing workflow alerts: {exc}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def acknowledge_engine_alert(
            self,
            alert_id: str,
            payload: wt.WorkflowEngineAlertAckRequest,
    ) -> wt.WorkflowEngineAlert:
        """标记告警为已知晓"""

        try:
            response = await self.infra_client.acknowledge_workflow_engine_alert(
                alert_id,
                payload.model_dump(exclude_none=True),
            )
            if not response.success:
                logger.error(f"Failed to acknowledge workflow alert {alert_id}: {response.error}")
                raise HTTPException(status_code=500, msg="Failed to acknowledge workflow alert")
            data = response.data or {}
            return wt.WorkflowEngineAlert(**data)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error acknowledging workflow alert {alert_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

    async def resolve_engine_alert(
            self,
            alert_id: str,
            payload: wt.WorkflowEngineAlertAckRequest,
    ) -> wt.WorkflowEngineAlert:
        """标记告警为已解决"""

        try:
            response = await self.infra_client.resolve_workflow_engine_alert(
                alert_id,
                payload.model_dump(exclude_none=True),
            )
            if not response.success:
                logger.error(f"Failed to resolve workflow alert {alert_id}: {response.error}")
                raise HTTPException(status_code=500, msg="Failed to resolve workflow alert")
            data = response.data or {}
            return wt.WorkflowEngineAlert(**data)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error resolving workflow alert {alert_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, msg="Internal server error")

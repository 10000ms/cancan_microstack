"""
工作流引擎 API 接口层
Workflow Engine API Interface Layer
"""
from datetime import datetime
from typing import (
    Dict,
    Any,
    Optional,
)

from fastapi import Query

from linglong_web import build_success_response
from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.infra import workflow as workflow_types
from cancan_microstack.services.infrasrv.application.workflow.workflow_app import workflow_app


async def create_workflow_handler(
        payload: workflow_types.WorkflowDefinitionCreate,
) -> APIResponse[workflow_types.WorkflowDefinition]:
    """
    创建一个新的工作流定义
    Create a new workflow definition.

    Args:
        payload: 工作流定义数据
                 Workflow definition data.

    Returns:
        已创建的工作流定义
        The created workflow definition.
    """
    result = await workflow_app.create_workflow_definition(payload)
    return build_success_response(data=result)


async def list_workflows_handler(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页大小"),
) -> APIResponse[workflow_types.WorkflowListResponse]:
    """
    列出所有工作流定义
    List all workflow definitions.

    Returns:
        工作流定义列表
        A list of workflow definitions.
    """
    result = await workflow_app.list_workflow_definitions(page, page_size)
    return build_success_response(data=result)


async def get_workflow_handler(
        workflow_id: str,
) -> APIResponse[workflow_types.WorkflowDefinition]:
    """
    根据 ID 获取指定的工作流定义
    Get a specific workflow definition by ID.

    Args:
        workflow_id: 工作流定义的唯一标识符
                     The unique identifier of the workflow definition.

    Returns:
        工作流定义
        The workflow definition.
    """
    result = await workflow_app.get_workflow_definition(workflow_id)
    return build_success_response(data=result)


async def list_workflow_versions_handler(
        workflow_id: str,
        limit: int = Query(50, ge=1, le=200, description="返回的版本数量限制"),
) -> APIResponse[workflow_types.WorkflowVersionListResponse]:
    """列出指定工作流的版本历史
    List workflow definition versions for the given workflow."""

    result = await workflow_app.list_workflow_versions(workflow_id, limit)
    return build_success_response(data=result)


async def list_runs_handler(
        workflow_id: Optional[str] = Query(None, description="按工作流ID过滤"),
        reqid: Optional[str] = Query(None, description="按请求追踪 ID 过滤"),
        status: Optional[str] = Query(None, description="运行状态过滤"),
        date_from: Optional[datetime] = Query(None, description="开始时间过滤"),
        date_to: Optional[datetime] = Query(None, description="结束时间过滤"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> APIResponse[workflow_types.WorkflowRunListResponse]:
    """
    列出工作流的运行实例
    List workflow runs.

    Args:
        workflow_id: (可选) 按工作流 ID 过滤
                     (Optional) Filter by workflow ID.
        page: 页码
              Page number.
          page_size: 每页大小
                 Size per page.

    Returns:
        工作流运行实例列表
        A list of workflow runs.
    """
    query = workflow_types.WorkflowRunQuery(
        workflow_id=workflow_id,
        reqid=reqid,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    result = await workflow_app.list_workflow_runs(query)
    return build_success_response(data=result)


async def trigger_workflow_handler(
        workflow_id: str, payload: workflow_types.WorkflowTriggerRequest,
) -> APIResponse[workflow_types.WorkflowTriggerResponse]:
    """
    触发一次工作流运行
    Trigger a workflow run.

    Args:
        workflow_id: 要触发的工作流的 ID
                     The ID of the workflow to trigger.
        payload: 触发工作流的上下文数据
                 The context data for triggering the workflow.

    Returns:
        包含运行 ID 和状态的字典
        A dictionary containing the run ID and status.
    """
    result = await workflow_app.trigger_workflow(workflow_id, payload)
    return build_success_response(data=result)


async def get_run_graph_status_handler(
        run_id: str,
) -> APIResponse[workflow_types.RunGraphResponse]:
    """
    获取工作流运行实例中所有节点的状态
    Get the status of all nodes in a workflow run graph.

    Args:
        run_id: 工作流运行实例的 ID
                The ID of the workflow run instance.

    Returns:
        节点状态列表
        A list of node statuses.
    """

    result = await workflow_app.get_run_graph_status(run_id)
    return build_success_response(data=result)


async def get_node_history_handler(
        run_id: str, node_id: str,
) -> APIResponse[workflow_types.NodeExecutionHistoryResponse]:
    """
    获取运行实例中特定节点的执行历史
    Get the execution history of a specific node in a run.

    Args:
        run_id: 工作流运行实例的 ID
                The ID of the workflow run instance.
        node_id: 节点的 ID
                 The ID of the node.

    Returns:
        节点的执行历史列表
        A list of execution history for the node.
    """
    result = await workflow_app.get_node_history(run_id, node_id)
    return build_success_response(data=result)


async def external_callback_handler(
        node_instance_id: str, payload: Dict[str, Any],
) -> APIResponse[workflow_types.CallbackAckResponse]:
    """
    处理等待外部回调的节点的恢复操作
    Handle external callbacks for suspended nodes.

    Args:
        node_instance_id: 节点实例的唯一标识符
                          The unique identifier of the node instance.
        payload: 外部服务返回的数据
                 Data returned from the external service.

    Returns:
        确认接受回调的状态
        A status confirming acceptance of the callback.
    """
    result = await workflow_app.handle_external_callback(node_instance_id, payload)
    return build_success_response(data=result)


async def get_workflow_stats_handler() -> APIResponse[workflow_types.WorkflowStats]:
    """
    获取工作流统计信息
    Get workflow statistics.

    Returns:
        工作流统计信息
        Workflow statistics.
    """
    result = await workflow_app.get_workflow_stats()
    return build_success_response(data=result)


async def update_workflow_handler(
        workflow_id: str,
        payload: workflow_types.WorkflowDefinitionUpdate,
) -> APIResponse[workflow_types.WorkflowDefinition]:
    """
    更新工作流定义
    Update workflow definition.

    Args:
        workflow_id: 工作流唯一标识符 / Workflow unique identifier.
        payload: 更新数据 / Update data.

    Returns:
        更新后的工作流定义 / The updated workflow definition.
    """
    result = await workflow_app.update_workflow_definition(workflow_id, payload)
    return build_success_response(data=result)


async def delete_workflow_handler(
        workflow_id: str,
) -> APIResponse[Dict[str, str]]:
    """
    删除工作流定义
    Delete workflow definition.

    Args:
        workflow_id: 工作流唯一标识符 / Workflow unique identifier.

    Returns:
        删除确认消息 / Deletion confirmation message.
    """
    await workflow_app.delete_workflow_definition(workflow_id)
    return build_success_response(data={"message": "Workflow deleted successfully"})


async def rollback_workflow_handler(
        workflow_id: str,
        payload: workflow_types.WorkflowRollbackRequest,
) -> APIResponse[workflow_types.WorkflowDefinition]:
    """回滚工作流定义到指定版本
    Roll back workflow definition to a historical version."""

    result = await workflow_app.rollback_workflow_definition(workflow_id, payload)
    return build_success_response(data=result)


async def list_engine_alerts_handler(
        status: Optional[workflow_types.WorkflowEngineAlertStatus] = Query(None, description="按状态过滤"),
        severity: Optional[workflow_types.WorkflowEngineAlertSeverity] = Query(None, description="按严重程度过滤"),
        run_id: Optional[str] = Query(None, description="按运行 ID 过滤"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=200, description="每页大小"),
) -> APIResponse[workflow_types.WorkflowEngineAlertListResponse]:
    """列出工作流引擎告警"""

    query = workflow_types.WorkflowEngineAlertQuery(
        status=status,
        severity=severity,
        run_id=run_id,
        page=page,
        page_size=page_size,
    )
    result = await workflow_app.list_engine_alerts(query)
    return build_success_response(data=result)


async def acknowledge_engine_alert_handler(
        alert_id: str,
        payload: workflow_types.WorkflowEngineAlertAckRequest,
) -> APIResponse[workflow_types.WorkflowEngineAlert]:
    """标记引擎告警为已知晓"""

    result = await workflow_app.acknowledge_engine_alert(alert_id, payload)
    return build_success_response(data=result)


async def resolve_engine_alert_handler(
        alert_id: str,
        payload: workflow_types.WorkflowEngineAlertAckRequest,
) -> APIResponse[workflow_types.WorkflowEngineAlert]:
    """标记引擎告警为已解决"""

    result = await workflow_app.resolve_engine_alert(alert_id, payload)
    return build_success_response(data=result)

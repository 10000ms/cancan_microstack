"""
工作流运维 API 路由处理器（opsbffsrv 层）
Workflow Operations API Handlers (opsbffsrv layer)

职责 / Responsibilities:
1. 参数校验和格式化 / Parameter validation and formatting
2. 转发请求到 infrasrv / Forward requests to infrasrv
3. 统一响应包装 / Unified response wrapping
4. 不包含业务逻辑 / No business logic here
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, Query

from linglong_web import build_success_response
from cancan_microstack.public.schemas.infra import workflow as wt
from cancan_microstack.services.opsbffsrv.application.workflow_ops_app import WorkflowOpsApp


# 本模块：Workflow 运维相关的 API 路由处理器（Handler）
# Module: API handlers for workflow operations in opsbffsrv
#
# 说明 / Description:
# 该文件定义了对外暴露的 workflow 运维相关的 HTTP handler（均为 async）。
# 1) 使用 FastAPI 的 Depends 注入 WorkflowOpsApp 的实例（get_workflow_app）。
# 2) 每个 handler 仅负责参数接收、调用应用层方法并通过统一响应构建器返回结果。
# 3) 不包含复杂业务逻辑，业务逻辑集中在 application 层（WorkflowOpsApp）。
# This module defines async HTTP handlers for workflow operations.
# 1) Handlers depend on WorkflowOpsApp via FastAPI Depends (get_workflow_app).
# 2) Each handler validates/receives params, calls application layer, and returns
#    a unified response via build_success_response.
# 3) No business logic here — business is implemented in WorkflowOpsApp.

def get_workflow_app() -> WorkflowOpsApp:
    """工厂函数，提供 WorkflowOpsApp 实例 / Factory to provide WorkflowOpsApp instance"""
    return WorkflowOpsApp()


# ==================== 工作流定义管理 / Workflow Definition Management ====================

async def list_workflows_handler(
        keyword: Optional[str] = Query(None, description="搜索关键词"),
        status: Optional[str] = Query(None, description="状态过滤: ACTIVE, INACTIVE"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页大小"),
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    列出所有工作流定义（支持分页和过滤）
    List all workflow definitions (with pagination and filtering)

    Args:
        keyword: 搜索关键词（匹配名称/标签）/ Search keyword (match name/tags)
        status: 状态过滤 / Status filter
        page: 页码 / Page number
        page_size: 每页大小 / Page size
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        工作流列表（分页）/ Paginated workflow list
    """
    query = wt.WorkflowListQuery(
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size
    )
    data = await app.list_workflows(query)
    return build_success_response(data=data)


async def get_workflow_handler(
        id: UUID,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    获取指定工作流详情
    Get workflow details by ID

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        工作流详情 / Workflow details
    """
    data = await app.get_workflow(str(id))
    return build_success_response(data=data)


async def create_workflow_handler(
        payload: wt.WorkflowDefinitionCreate,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    创建新工作流
    Create a new workflow

    Args:
        payload: 工作流定义数据 / Workflow definition data
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        已创建的工作流 / Created workflow
    """
    data = await app.create_workflow(payload)
    return build_success_response(data=data)


async def update_workflow_handler(
        id: UUID,
        payload: wt.WorkflowDefinitionUpdate,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    更新工作流定义
    Update workflow definition

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        payload: 更新数据 / Update data
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        更新后的工作流 / Updated workflow
    """
    data = await app.update_workflow(str(id), payload)
    return build_success_response(data=data)


async def delete_workflow_handler(
        id: UUID,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    删除工作流
    Delete workflow

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        删除确认 / Deletion confirmation
    """
    await app.delete_workflow(str(id))
    return build_success_response(data={"message": "Workflow deleted successfully"})


async def toggle_workflow_handler(
        id: UUID,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    切换工作流启用状态
    Toggle workflow active status

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        更新后的工作流 / Updated workflow
    """
    data = await app.toggle_workflow(str(id))
    return build_success_response(data=data)


async def duplicate_workflow_handler(
        id: UUID,
        payload: wt.DuplicateWorkflowPayload,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    复制工作流
    Duplicate workflow

    Args:
        id: 源工作流唯一标识符 / Source workflow unique identifier
        payload: 复制配置（新名称等）/ Duplication config (new name, etc.)
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        复制后的工作流 / Duplicated workflow
    """
    data = await app.duplicate_workflow(str(id), payload)
    return build_success_response(data=data)


async def list_workflow_versions_handler(
        id: UUID,
        limit: int = Query(50, ge=1, le=200, description="返回版本数量限制"),
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """列出工作流版本历史
    List workflow definition versions"""

    data = await app.list_workflow_versions(str(id), limit)
    return build_success_response(data=data)


async def rollback_workflow_handler(
        id: UUID,
        payload: wt.WorkflowRollbackRequest,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """回滚工作流定义
    Roll back workflow definition"""

    data = await app.rollback_workflow(str(id), payload)
    return build_success_response(data=data)


async def publish_workflow_handler(
        id: UUID,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    发布工作流（标记为生产就绪）
    Publish workflow (mark as production-ready)

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        发布后的工作流 / Published workflow
    """
    data = await app.publish_workflow(str(id))
    return build_success_response(data=data)


async def validate_workflow_handler(
        id: UUID,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    验证工作流定义
    Validate workflow definition

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        验证结果 / Validation result
    """
    data = await app.validate_workflow(str(id))
    return build_success_response(data=data)


# ==================== 工作流统计 / Workflow Statistics ====================

async def get_workflow_stats_handler(
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    获取工作流统计概览
    Get workflow statistics overview

    Args:
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        统计信息 / Statistics
    """
    data = await app.get_workflow_stats()
    return build_success_response(data=data)


# ==================== 工作流运行管理 / Workflow Run Management ====================

async def trigger_workflow_handler(
        id: UUID,
        payload: wt.WorkflowTriggerRequest,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    手动触发工作流运行
    Manually trigger workflow run

    Args:
        id: 工作流唯一标识符 / Workflow unique identifier
        payload: 触发上下文数据 / Trigger context data
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        运行实例信息 / Run instance info
    """
    data = await app.trigger_workflow(str(id), payload)
    return build_success_response(data=data)


async def list_runs_handler(
        workflow_id: Optional[str] = Query(None, description="按工作流ID过滤"),
    reqid: Optional[str] = Query(None, description="按请求追踪 ID 过滤"),
        status: Optional[str] = Query(None, description="运行状态过滤"),
        date_from: Optional[str] = Query(None, description="开始时间"),
        date_to: Optional[str] = Query(None, description="结束时间"),
        page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    列出工作流运行实例（支持过滤和分页）
    List workflow runs (with filtering and pagination)

    Args:
        workflow_id: 按工作流ID过滤 / Filter by workflow ID
        page: 页码 / Page number
        page_size: 每页大小 / Page size
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        运行实例列表 / Run instance list
    """
    data = await app.list_runs(
        workflow_id=workflow_id,
        reqid=reqid,
        page=page,
        page_size=page_size,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    return build_success_response(data=data)


async def get_run_graph_status_handler(
    run_id: str,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    获取运行图状态（用于可视化展示）
    Get run graph status (for visualization)

    Args:
        run_id: 运行实例唯一标识符 / Run instance unique identifier
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        图状态数据（节点+边）/ Graph status data (nodes + edges)
    """
    data = await app.get_run_graph_status(run_id)
    return build_success_response(data=data)


async def get_node_history_handler(
        run_id: str,
        node_id: str,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """
    获取节点执行历史
    Get node execution history

    Args:
        run_id: 运行实例唯一标识符 / Run instance unique identifier
        node_id: 节点ID / Node ID
        app: WorkflowOpsApp 实例 / WorkflowOpsApp instance

    Returns:
        节点执行历史（含日志）/ Node execution history (with logs)
    """
    data = await app.get_node_history(run_id, node_id)
    return build_success_response(data=data)


# ==================== Workflow Engine Alerts ====================


async def list_workflow_alerts_handler(
        status: Optional[wt.WorkflowEngineAlertStatus] = Query(None, description="状态过滤"),
        severity: Optional[wt.WorkflowEngineAlertSeverity] = Query(None, description="严重程度过滤"),
        run_id: Optional[str] = Query(None, description="运行ID过滤"),
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=200, description="每页大小"),
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """列出工作流引擎告警"""

    query = wt.WorkflowEngineAlertQuery(
        status=status,
        severity=severity,
        run_id=run_id,
        page=page,
        page_size=page_size,
    )
    data = await app.list_engine_alerts(query)
    return build_success_response(data=data)


async def acknowledge_workflow_alert_handler(
        alert_id: str,
        payload: wt.WorkflowEngineAlertAckRequest,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """标记告警为已知晓"""

    data = await app.acknowledge_engine_alert(alert_id, payload)
    return build_success_response(data=data)


async def resolve_workflow_alert_handler(
        alert_id: str,
        payload: wt.WorkflowEngineAlertAckRequest,
        app: WorkflowOpsApp = Depends(get_workflow_app)
):
    """标记告警为已解决"""

    data = await app.resolve_engine_alert(alert_id, payload)
    return build_success_response(data=data)

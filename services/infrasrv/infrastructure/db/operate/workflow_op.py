"""
工作流引擎数据库操作
Workflow engine database operations
"""
import uuid
from datetime import (
    datetime,
    timezone,
    timedelta,
)
from typing import (
    List,
    Optional,
    Dict,
    Any,
    Tuple,
)

from sqlalchemy import (
    select,
    desc,
    and_,
    or_,
    update,
    func,
)
from sqlalchemy.dialects.postgresql import insert

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra import workflow as workflow_types
from cancan_microstack.public.schemas.infra.enums import (
    WorkflowStatus,
    NodeStatus,
    ExecutionLogStatus,
    WorkflowEngineAlertStatus,
)
from cancan_microstack.services.infrasrv.infrastructure.db.model.workflow_run_tbl import WorkflowRunTbl
from cancan_microstack.services.infrasrv.infrastructure.db.model.workflow_definition_tbl import WorkflowDefinitionTbl
from cancan_microstack.services.infrasrv.infrastructure.db.model.workflow_definition_version_tbl import \
    WorkflowDefinitionVersionTbl
from cancan_microstack.services.infrasrv.infrastructure.db.model.node_instance_tbl import NodeInstanceTbl
from cancan_microstack.services.infrasrv.infrastructure.db.model.execution_log_tbl import ExecutionLogTbl
from cancan_microstack.services.infrasrv.infrastructure.db.model.workflow_engine_alert_tbl import WorkflowEngineAlertTbl


async def _insert_version_snapshot(session, workflow_row, change_summary: Optional[str]) -> None:
    """写入工作流版本快照
    Persist a workflow definition snapshot for version tracking"""

    snapshot_values = {
        "workflow_id": workflow_row.id,
        "version": getattr(workflow_row, "version", 1),
        "name": workflow_row.name,
        "description": workflow_row.description,
        "schedule": workflow_row.schedule,
        "graph_data": workflow_row.graph_data,
        "nodes_config": workflow_row.nodes_config,
        "global_context": workflow_row.global_context,
        "is_active": workflow_row.is_active,
        "change_summary": change_summary,
    }
    await session.execute(
        insert(WorkflowDefinitionVersionTbl).values(**snapshot_values)
    )


# 工作流运行终态集合，用于计算耗时并停止派发
# Set of terminal workflow statuses used to finalize runtime bookkeeping
TERMINAL_WORKFLOW_STATUSES = {
    WorkflowStatus.SUCCESS,
    WorkflowStatus.FAILURE,
    WorkflowStatus.CANCELLED,
}


async def create_workflow_definition(
        data: workflow_types.WorkflowDefinitionCreate) -> workflow_types.WorkflowDefinition:
    """创建工作流定义记录 / Insert a workflow definition row."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            payload = data.model_dump()
            payload.setdefault("version", 1)
            stmt = insert(WorkflowDefinitionTbl).values(**payload).returning(WorkflowDefinitionTbl)
            row = (await session.execute(stmt)).scalar_one()
            await _insert_version_snapshot(session, row, change_summary="Initial version")
            return workflow_types.WorkflowDefinition.model_validate(row, from_attributes=True)


async def list_workflow_definitions(
        limit: int = 100,
        offset: int = 0,
) -> Tuple[List[workflow_types.WorkflowDefinition], int]:
    """分页查询工作流定义并返回总数 / List workflow definitions with pagination and total."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            base_stmt = select(WorkflowDefinitionTbl).where(WorkflowDefinitionTbl.flag == 0)
            total_stmt = select(func.count()).select_from(base_stmt.subquery())
            total = (await session.execute(total_stmt)).scalar_one()

            stmt = (
                base_stmt.order_by(desc(WorkflowDefinitionTbl.update_time))
                .limit(limit)
                .offset(offset)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            definitions = [workflow_types.WorkflowDefinition.model_validate(r, from_attributes=True) for r in rows]
            return definitions, total


async def get_workflow_definition_by_id(workflow_id: uuid.UUID) -> Optional[workflow_types.WorkflowDefinition]:
    """按ID获取工作流定义 / Fetch workflow definition by primary key."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(WorkflowDefinitionTbl).where(WorkflowDefinitionTbl.id == workflow_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.WorkflowDefinition.model_validate(row, from_attributes=True) if row else None


async def update_workflow_definition(
        workflow_id: uuid.UUID,
        data: workflow_types.WorkflowDefinitionUpdate,
) -> Optional[workflow_types.WorkflowDefinition]:
    """更新工作流定义并写入版本快照
    Update workflow definition fields and record a version snapshot."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            current_stmt = select(WorkflowDefinitionTbl).where(WorkflowDefinitionTbl.id == workflow_id)
            current_row = (await session.execute(current_stmt)).scalar_one_or_none()
            if not current_row:
                return None

            update_dict = data.model_dump(exclude_unset=True)
            change_summary = update_dict.pop("change_summary", data.change_summary)
            new_version = (current_row.version or 1) + 1
            update_dict["version"] = new_version
            if change_summary:
                update_dict["change_summary"] = change_summary

            stmt = (
                update(WorkflowDefinitionTbl)
                .where(WorkflowDefinitionTbl.id == workflow_id)
                .values(**update_dict)
                .returning(WorkflowDefinitionTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                await _insert_version_snapshot(session, row, change_summary or "Definition updated")
                return workflow_types.WorkflowDefinition.model_validate(row, from_attributes=True)
            return None


async def get_scheduled_workflows() -> List[workflow_types.WorkflowDefinition]:
    """获取启用的定时工作流 / Fetch active workflows that own schedules."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(WorkflowDefinitionTbl).where(
                and_(
                    WorkflowDefinitionTbl.flag == 0,
                    WorkflowDefinitionTbl.is_active == True,
                    WorkflowDefinitionTbl.schedule != None,
                    WorkflowDefinitionTbl.schedule != ''
                )
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return [workflow_types.WorkflowDefinition.model_validate(r, from_attributes=True) for r in rows]


async def list_workflow_versions(
        workflow_id: uuid.UUID,
        limit: int = 50,
) -> List[workflow_types.WorkflowDefinitionVersion]:
    """列出工作流版本历史
    List workflow definition versions (most recent first)."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                select(WorkflowDefinitionVersionTbl)
                .where(WorkflowDefinitionVersionTbl.workflow_id == workflow_id)
                .order_by(desc(WorkflowDefinitionVersionTbl.version))
                .limit(limit)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return [workflow_types.WorkflowDefinitionVersion.model_validate(r, from_attributes=True) for r in rows]


async def get_workflow_version(
        workflow_id: uuid.UUID,
        version: int,
) -> Optional[workflow_types.WorkflowDefinitionVersion]:
    """获取指定版本快照 / Fetch an individual workflow version snapshot."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(WorkflowDefinitionVersionTbl).where(
                and_(
                    WorkflowDefinitionVersionTbl.workflow_id == workflow_id,
                    WorkflowDefinitionVersionTbl.version == version,
                )
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.WorkflowDefinitionVersion.model_validate(row, from_attributes=True) if row else None


async def rollback_workflow_definition(
        workflow_id: uuid.UUID,
        target_version: int,
        reason: Optional[str] = None,
) -> Optional[workflow_types.WorkflowDefinition]:
    """回滚到指定版本并生成新版本
    Restore workflow definition to a historical version and emit a new version snapshot."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            snapshot_stmt = select(WorkflowDefinitionVersionTbl).where(
                and_(
                    WorkflowDefinitionVersionTbl.workflow_id == workflow_id,
                    WorkflowDefinitionVersionTbl.version == target_version,
                )
            )
            snapshot = (await session.execute(snapshot_stmt)).scalar_one_or_none()
            if not snapshot:
                return None

            current_stmt = select(WorkflowDefinitionTbl).where(WorkflowDefinitionTbl.id == workflow_id)
            current_row = (await session.execute(current_stmt)).scalar_one_or_none()
            if not current_row:
                return None

            new_version = (current_row.version or 1) + 1
            summary = reason or f"Rollback to v{target_version}"
            update_values = {
                "name": snapshot.name,
                "description": snapshot.description,
                "schedule": snapshot.schedule,
                "graph_data": snapshot.graph_data,
                "nodes_config": snapshot.nodes_config,
                "global_context": snapshot.global_context,
                "is_active": snapshot.is_active,
                "version": new_version,
                "change_summary": summary,
            }
            stmt = (
                update(WorkflowDefinitionTbl)
                .where(WorkflowDefinitionTbl.id == workflow_id)
                .values(**update_values)
                .returning(WorkflowDefinitionTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                await _insert_version_snapshot(session, row, summary)
                return workflow_types.WorkflowDefinition.model_validate(row, from_attributes=True)
            return None


# --- 工作流运行操作 / WorkflowRun Operations ---

async def create_workflow_run(data: workflow_types.WorkflowRunCreate) -> workflow_types.WorkflowRun:
    """创建工作流运行实例 / Insert workflow run row when triggering workflows."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = insert(WorkflowRunTbl).values(**data.model_dump()).returning(WorkflowRunTbl)
            row = (await session.execute(stmt)).scalar_one()
            return workflow_types.WorkflowRun.model_validate(row, from_attributes=True)


async def list_workflow_runs(
        workflow_id: Optional[uuid.UUID] = None,
    reqid: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        status: Optional[WorkflowStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
) -> Tuple[List[workflow_types.WorkflowRun], int]:
    """查询运行实例列表 / List workflow runs optionally filtered by workflow ID, status, or time window."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            filters = [WorkflowRunTbl.flag == 0]
            if workflow_id:
                filters.append(WorkflowRunTbl.workflow_id == workflow_id)
            if reqid:
                normalized_reqid = reqid.strip()
                if normalized_reqid:
                    filters.append(
                        or_(
                            WorkflowRunTbl.trigger_context["reqid"].astext == normalized_reqid,
                            WorkflowRunTbl.global_context["reqid"].astext == normalized_reqid,
                        )
                    )
            if status:
                filters.append(WorkflowRunTbl.status == status.value)
            if date_from:
                filters.append(WorkflowRunTbl.started_at >= date_from)
            if date_to:
                filters.append(WorkflowRunTbl.started_at <= date_to)

            base_stmt = select(WorkflowRunTbl)
            if filters:
                base_stmt = base_stmt.where(and_(*filters))

            total_stmt = select(func.count()).select_from(base_stmt.subquery())
            total = (await session.execute(total_stmt)).scalar_one()

            stmt = (
                base_stmt.order_by(desc(WorkflowRunTbl.started_at))
                .limit(limit)
                .offset(offset)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            runs = [workflow_types.WorkflowRun.model_validate(r, from_attributes=True) for r in rows]
            return runs, total


async def get_workflow_run_by_id(run_id: uuid.UUID) -> Optional[workflow_types.WorkflowRun]:
    """按ID查询运行实例 / Fetch workflow run by primary key."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(WorkflowRunTbl).where(WorkflowRunTbl.id == run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.WorkflowRun.model_validate(row, from_attributes=True) if row else None


async def update_workflow_run_status(run_id: uuid.UUID, status: WorkflowStatus) -> Optional[workflow_types.WorkflowRun]:
    """更新工作流运行状态并计算耗时 / Update workflow run status and compute duration."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            current_stmt = select(WorkflowRunTbl).where(WorkflowRunTbl.id == run_id)
            current = (await session.execute(current_stmt)).scalar_one_or_none()
            if not current:
                return None

            now = datetime.now(timezone.utc)
            update_values = {
                "status": status.value,
            }
            if status in TERMINAL_WORKFLOW_STATUSES:
                update_values["finished_at"] = now
                if current.started_at:
                    duration_ms = int((now - current.started_at).total_seconds() * 1000)
                    update_values["duration_ms"] = duration_ms

            stmt = (
                update(WorkflowRunTbl)
                .where(WorkflowRunTbl.id == run_id)
                .values(**update_values)
                .returning(WorkflowRunTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.WorkflowRun.model_validate(row, from_attributes=True) if row else None


async def update_workflow_run_global_context(
        run_id: uuid.UUID,
        global_context: Dict[str, Any],
) -> Optional[workflow_types.WorkflowRun]:
    """更新工作流运行的全局上下文 / Update workflow run global context."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                update(WorkflowRunTbl)
                .where(WorkflowRunTbl.id == run_id)
                .values(global_context=global_context)
                .returning(WorkflowRunTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.WorkflowRun.model_validate(row, from_attributes=True) if row else None


# --- 节点实例操作 / NodeInstance Operations ---

async def get_node_instances_by_run_id(run_id: uuid.UUID) -> List[workflow_types.NodeInstance]:
    """查询指定运行的全部节点实例 / List all node instances for a run."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(NodeInstanceTbl).where(NodeInstanceTbl.run_id == run_id).order_by(NodeInstanceTbl.loop_index)
            rows = list((await session.execute(stmt)).scalars().all())
            return [workflow_types.NodeInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_node_instances_by_run_and_node_id(run_id: uuid.UUID, node_id: str) -> List[workflow_types.NodeInstance]:
    """查询某运行中某节点的全部实例 / Fetch node instances filtered by run and node ID."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(NodeInstanceTbl).where(
                and_(
                    NodeInstanceTbl.run_id == run_id,
                    NodeInstanceTbl.node_id == node_id
                )
            ).order_by(NodeInstanceTbl.loop_index)
            rows = list((await session.execute(stmt)).scalars().all())
            return [workflow_types.NodeInstance.model_validate(r, from_attributes=True) for r in rows]


async def get_node_instance_by_id(instance_id: uuid.UUID) -> Optional[workflow_types.NodeInstance]:
    """按节点实例 ID 查询记录 / Fetch node instance by primary key."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(NodeInstanceTbl).where(NodeInstanceTbl.id == instance_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.NodeInstance.model_validate(row, from_attributes=True) if row else None


async def upsert_node_instance(run_id: uuid.UUID, node_id: str, loop_index: int) -> workflow_types.NodeInstance:
    """插入或更新节点实例（用于记录重试次数）/ Upsert a node instance to track attempts."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                insert(NodeInstanceTbl)
                .values(
                    run_id=run_id,
                    node_id=node_id,
                    loop_index=loop_index,
                    status=NodeStatus.RUNNING.value,
                    attempt_count=1,
                )
                .on_conflict_do_update(
                    index_elements=["run_id", "node_id", "loop_index"],
                    set_={
                        "status": NodeStatus.RUNNING.value,
                        "attempt_count": NodeInstanceTbl.attempt_count + 1,
                        "update_time": func.current_timestamp(),
                    },
                )
                .returning(NodeInstanceTbl)
            )
            row = (await session.execute(stmt)).scalar_one()
            return workflow_types.NodeInstance.model_validate(row, from_attributes=True)


async def update_node_instance_result(
        instance_id: uuid.UUID,
        status: NodeStatus,
        final_output: Optional[Dict[str, Any]] = None,
        error_msg: Optional[str] = None,
) -> Optional[workflow_types.NodeInstance]:
    """更新节点执行结果 / Persist node execution result payload."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            update_values: Dict[str, Any] = {
                "status": status.value,
                "final_output": final_output,
                "error_msg": error_msg,
                "update_time": func.current_timestamp(),
            }
            stmt = (
                update(NodeInstanceTbl)
                .where(NodeInstanceTbl.id == instance_id)
                .values(**update_values)
                .returning(NodeInstanceTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.NodeInstance.model_validate(row, from_attributes=True) if row else None


# --- 执行日志操作 / ExecutionLog Operations ---

async def create_execution_log(
        node_instance_id: uuid.UUID,
        attempt_no: int,
        request_snapshot: Optional[Dict[str, Any]] = None,
) -> workflow_types.ExecutionLog:
    """创建执行日志记录 / Create execution log entry."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                insert(ExecutionLogTbl)
                .values(
                    node_instance_id=node_instance_id,
                    attempt_no=attempt_no,
                    request_snapshot=request_snapshot,
                    status=ExecutionLogStatus.PENDING.value,
                )
                .returning(ExecutionLogTbl)
            )
            row = (await session.execute(stmt)).scalar_one()
            return workflow_types.ExecutionLog.model_validate(row, from_attributes=True)


async def update_execution_log_result(
        log_id: uuid.UUID,
        status: ExecutionLogStatus,
        response_snapshot: Optional[Dict[str, Any]] = None,
        error_detail: Optional[str] = None,
) -> Optional[workflow_types.ExecutionLog]:
    """更新执行日志的结果 / Update execution log outcome."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            current_stmt = select(ExecutionLogTbl).where(ExecutionLogTbl.id == log_id)
            current = (await session.execute(current_stmt)).scalar_one_or_none()
            if not current:
                return None

            now = datetime.now(timezone.utc)
            duration_ms = None
            if current.start_time:
                duration_ms = int((now - current.start_time).total_seconds() * 1000)

            update_values: Dict[str, Any] = {
                "status": status.value,
                "response_snapshot": response_snapshot,
                "error_detail": error_detail,
                "end_time": now,
            }
            if duration_ms is not None:
                update_values["duration_ms"] = duration_ms

            stmt = (
                update(ExecutionLogTbl)
                .where(ExecutionLogTbl.id == log_id)
                .values(**update_values)
                .returning(ExecutionLogTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.ExecutionLog.model_validate(row, from_attributes=True) if row else None


async def get_execution_logs_by_node_instance_id(node_instance_id: uuid.UUID) -> List[workflow_types.ExecutionLog]:
    """查询节点实例的执行日志 / Fetch execution logs for a node instance."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ExecutionLogTbl).where(ExecutionLogTbl.node_instance_id == node_instance_id).order_by(
                ExecutionLogTbl.attempt_no)
            rows = list((await session.execute(stmt)).scalars().all())
            return [workflow_types.ExecutionLog.model_validate(r, from_attributes=True) for r in rows]


async def get_workflow_stats() -> workflow_types.WorkflowStats:
    """获取工作流统计信息 / Fetch workflow statistics with recent run metrics."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            active_filter = WorkflowDefinitionTbl.flag == 0
            total_defs = await session.scalar(
                select(func.count()).select_from(WorkflowDefinitionTbl).where(active_filter))
            active_defs = await session.scalar(
                select(func.count())
                .select_from(WorkflowDefinitionTbl)
                .where(and_(active_filter, WorkflowDefinitionTbl.is_active == True))
            )
            scheduled_defs = await session.scalar(
                select(func.count())
                .select_from(WorkflowDefinitionTbl)
                .where(
                    and_(
                        active_filter,
                        WorkflowDefinitionTbl.is_active == True,
                        WorkflowDefinitionTbl.schedule != None,
                        WorkflowDefinitionTbl.schedule != ''
                    )
                )
            )

            run_active_filter = WorkflowRunTbl.flag == 0
            total_runs = await session.scalar(
                select(func.count()).select_from(WorkflowRunTbl).where(run_active_filter)
            )
            running_runs = await session.scalar(
                select(func.count()).select_from(WorkflowRunTbl).where(
                    and_(run_active_filter, WorkflowRunTbl.status == WorkflowStatus.RUNNING.value)
                )
            ) or 0
            pending_runs = await session.scalar(
                select(func.count()).select_from(WorkflowRunTbl).where(
                    and_(run_active_filter, WorkflowRunTbl.status == WorkflowStatus.PENDING.value)
                )
            ) or 0

            runs_by_status_stmt = (
                select(WorkflowRunTbl.status, func.count(WorkflowRunTbl.id))
                .where(run_active_filter)
                .group_by(WorkflowRunTbl.status)
            )
            runs_by_status_res = (await session.execute(runs_by_status_stmt)).all()
            runs_by_status = {str(status): count for status, count in runs_by_status_res}

            now = datetime.now(timezone.utc)
            since_24h = now - timedelta(hours=24)
            last_24h_filter = and_(run_active_filter, WorkflowRunTbl.started_at >= since_24h)

            runs_today = await session.scalar(
                select(func.count()).select_from(WorkflowRunTbl).where(last_24h_filter)
            ) or 0
            failed_runs_today = await session.scalar(
                select(func.count())
                .select_from(WorkflowRunTbl)
                .where(and_(last_24h_filter, WorkflowRunTbl.status == WorkflowStatus.FAILURE.value))
            ) or 0
            success_24h = await session.scalar(
                select(func.count())
                .select_from(WorkflowRunTbl)
                .where(and_(last_24h_filter, WorkflowRunTbl.status == WorkflowStatus.SUCCESS.value))
            ) or 0
            success_rate_24h = float(success_24h) / runs_today * 100 if runs_today else 0.0

            node_active_filter = NodeInstanceTbl.flag == 0
            active_node_statuses = [
                NodeStatus.RUNNING.value,
                NodeStatus.SUSPENDED.value,
                NodeStatus.RETRYING.value,
            ]
            active_node_instances = await session.scalar(
                select(func.count()).select_from(NodeInstanceTbl).where(
                    and_(node_active_filter, NodeInstanceTbl.status.in_(active_node_statuses))
                )
            ) or 0
            waiting_node_instances = await session.scalar(
                select(func.count()).select_from(NodeInstanceTbl).where(
                    and_(node_active_filter, NodeInstanceTbl.status == NodeStatus.PENDING.value)
                )
            ) or 0

            inflight_attempts = await session.scalar(
                select(func.count()).select_from(ExecutionLogTbl).where(
                    and_(
                        ExecutionLogTbl.flag == 0,
                        or_(
                            ExecutionLogTbl.status == None,
                            ExecutionLogTbl.status == ExecutionLogStatus.PENDING.value,
                        ),
                        ExecutionLogTbl.end_time == None,
                    )
                )
            ) or 0

            return workflow_types.WorkflowStats(
                total_definitions=total_defs or 0,
                active_definitions=active_defs or 0,
                scheduled_definitions=scheduled_defs or 0,
                total_runs=total_runs or 0,
                runs_by_status=runs_by_status,
                runs_today=runs_today,
                failed_runs_today=failed_runs_today,
                success_rate_24h=round(success_rate_24h, 2),
                running_runs=running_runs,
                pending_runs=pending_runs,
                active_node_instances=active_node_instances,
                waiting_node_instances=waiting_node_instances,
                inflight_attempts=inflight_attempts,
            )


# --- Engine Alert Operations ---

async def create_engine_alert(
        data: workflow_types.WorkflowEngineAlertCreate,
) -> workflow_types.WorkflowEngineAlert:
    """创建引擎告警记录 / Persist a workflow engine alert entry."""

    payload = data.model_dump(mode="json", exclude_none=True)
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = (
                insert(WorkflowEngineAlertTbl)
                .values(**payload)
                .returning(WorkflowEngineAlertTbl)
            )
            row = (await session.execute(stmt)).scalar_one()
            return workflow_types.WorkflowEngineAlert.model_validate(row, from_attributes=True)


async def list_engine_alerts(
        query: workflow_types.WorkflowEngineAlertQuery,
) -> workflow_types.WorkflowEngineAlertListResponse:
    """查询引擎告警列表 / List workflow engine alerts with pagination."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            filters = [WorkflowEngineAlertTbl.flag == 0]
            if query.status:
                filters.append(WorkflowEngineAlertTbl.status == query.status.value)
            if query.severity:
                filters.append(WorkflowEngineAlertTbl.severity == query.severity.value)
            if query.run_id:
                try:
                    run_uuid = uuid.UUID(query.run_id)
                    filters.append(WorkflowEngineAlertTbl.run_id == run_uuid)
                except ValueError:
                    filters.append(WorkflowEngineAlertTbl.run_id == uuid.UUID(int=0))

            base_stmt = select(WorkflowEngineAlertTbl)
            if filters:
                base_stmt = base_stmt.where(and_(*filters))

            total_stmt = select(func.count()).select_from(base_stmt.subquery())
            total = (await session.execute(total_stmt)).scalar_one() or 0

            stmt = (
                base_stmt
                .order_by(desc(WorkflowEngineAlertTbl.created_time))
                .limit(query.page_size)
                .offset((query.page - 1) * query.page_size)
            )
            rows = list((await session.execute(stmt)).scalars().all())
            alerts = [workflow_types.WorkflowEngineAlert.model_validate(r, from_attributes=True) for r in rows]
            return workflow_types.WorkflowEngineAlertListResponse(
                list=alerts,
                total=total,
                page=query.page,
                page_size=query.page_size,
            )


async def acknowledge_engine_alert(
        alert_id: uuid.UUID,
        operator: Optional[str],
        note: Optional[str] = None,
) -> Optional[workflow_types.WorkflowEngineAlert]:
    """标记引擎告警为已知晓 / Mark an engine alert as acknowledged."""

    return await _update_engine_alert(
        alert_id,
        WorkflowEngineAlertStatus.ACKED,
        operator,
        note,
        mutate_ack=True,
    )


async def resolve_engine_alert(
        alert_id: uuid.UUID,
        operator: Optional[str],
        note: Optional[str] = None,
) -> Optional[workflow_types.WorkflowEngineAlert]:
    """标记引擎告警为已解决 / Mark an engine alert as resolved."""

    return await _update_engine_alert(
        alert_id,
        WorkflowEngineAlertStatus.RESOLVED,
        operator,
        note,
        mutate_resolved=True,
    )


async def _update_engine_alert(
        alert_id: uuid.UUID,
        status: WorkflowEngineAlertStatus,
        operator: Optional[str],
        note: Optional[str],
        *,
        mutate_ack: bool = False,
        mutate_resolved: bool = False,
) -> Optional[workflow_types.WorkflowEngineAlert]:
    """内部通用方法：更新告警状态 / Internal helper to update alert status fields."""

    async with Rmanager.pg_session() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)
            update_values: Dict[str, Any] = {
                "status": status.value,
                "update_time": func.current_timestamp(),
            }
            if note is not None:
                update_values["note"] = note

            if mutate_ack:
                update_values.update(
                    {
                        "acknowledged_by": operator,
                        "acknowledged_at": now,
                    }
                )
            if mutate_resolved:
                update_values.update(
                    {
                        "resolved_by": operator,
                        "resolved_at": now,
                    }
                )
                # 如果之前未标记 ack，则同步填充
                update_values.setdefault("acknowledged_by", operator)
                update_values.setdefault("acknowledged_at", now)

            status_filter = []
            if mutate_ack:
                status_filter.append(WorkflowEngineAlertTbl.status == WorkflowEngineAlertStatus.OPEN.value)
            elif mutate_resolved:
                status_filter.append(WorkflowEngineAlertTbl.status != WorkflowEngineAlertStatus.RESOLVED.value)

            stmt = (
                update(WorkflowEngineAlertTbl)
                .where(
                    and_(
                        WorkflowEngineAlertTbl.id == alert_id,
                        WorkflowEngineAlertTbl.flag == 0,
                        *status_filter,
                    )
                )
                .values(**update_values)
                .returning(WorkflowEngineAlertTbl)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return workflow_types.WorkflowEngineAlert.model_validate(row, from_attributes=True) if row else None

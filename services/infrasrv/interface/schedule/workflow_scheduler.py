"""
Workflow Scheduler Task
"""
from datetime import (
    datetime,
    timedelta,
)
from typing import Optional

from croniter import croniter

from cancan_microstack.public.schemas.infra import workflow as workflow_types
from linglong_web.utils import (
    get_request_id,
    logger,
    set_request_id,
)

from cancan_microstack.services.infrasrv.application.workflow.workflow_app import workflow_app


async def workflow_scheduler_task():
    """扫描并触发需要调度的工作流
    Scan for due workflows and trigger them via the workflow app.
    """
    logger.info("Workflow scheduler task started.")
    try:
        await scan_and_trigger_workflows()
    except Exception as exc:
        logger.error(f"Error in workflow scheduler: {exc}", exc_info=True)


async def scan_and_trigger_workflows(reference_time: Optional[datetime] = None):
    """Scan registered definitions and trigger due workflows.
    扫描已注册的工作流定义并触发符合条件的调度。
    """

    now = (reference_time or datetime.now()).replace(microsecond=0)
    scheduled_workflows = await workflow_app.get_scheduled_workflows()

    if not scheduled_workflows:
        logger.info("No scheduled workflows found.")
        return

    triggered_count = 0
    for workflow in scheduled_workflows:
        cron_expr = (workflow.schedule or "").strip()
        if not cron_expr:
            logger.warning(f"Empty cron string for workflow {workflow.id}")
            continue

        second_at_beginning = _cron_has_seconds(cron_expr)
        if not croniter.is_valid(cron_expr, second_at_beginning=second_at_beginning):
            logger.warning(f"Invalid cron string for workflow {workflow.id}: {workflow.schedule}")
            continue

        base_time = _normalize_base_time(cron_expr, now)
        if not _cron_due(cron_expr, base_time):
            continue

        logger.info(f"Triggering scheduled workflow: {workflow.name} ({workflow.id})")
        try:
            # 每个调度触发分配独立 reqid，便于全链路检索
            # Allocate dedicated reqid per scheduled trigger for end-to-end traceability
            set_request_id(None)
            scheduled_reqid = get_request_id()
            await workflow_app.trigger_workflow(
                workflow_id_str=str(workflow.id),
                payload=workflow_types.WorkflowTriggerRequest(
                    trigger_context={
                        "scheduled_time": base_time.isoformat(),
                        "reqid": scheduled_reqid,
                    }
                ),
                trigger_type=workflow_types.TriggerType.SCHEDULE,
            )
            triggered_count += 1
        except Exception as e:
            logger.error(f"Failed to trigger workflow {workflow.id}: {e}", exc_info=True)

    logger.info(f"Workflow scheduler task finished. Triggered {triggered_count} workflows.")


def _cron_due(expression: str, base_time: datetime) -> bool:
    """Return True when the cron expression fires near *base_time*.
    当 cron 表达式在基准时间附近触发时返回 True。
    """

    try:
        second_at_beginning = _cron_has_seconds(expression)
        cron = croniter(
            expression,
            base_time + timedelta(seconds=1),
            second_at_beginning=second_at_beginning,
        )
        prev_fire = cron.get_prev(datetime)
    except Exception as exc:  # noqa: BLE001 - croniter raises generic exceptions
        logger.warning("Failed to iterate cron '%s': %s", expression, exc)
        return False

    tolerance_seconds = 1 if _cron_has_seconds(expression) else 60
    delta = (base_time - prev_fire).total_seconds()
    return 0 <= delta <= tolerance_seconds


def _cron_has_seconds(expression: str) -> bool:
    parts = [part for part in expression.split() if part]
    return len(parts) >= 6


def _normalize_base_time(expression: str, reference_time: datetime) -> datetime:
    normalized = reference_time.replace(microsecond=0)
    if _cron_has_seconds(expression):
        return normalized
    return normalized.replace(second=0)

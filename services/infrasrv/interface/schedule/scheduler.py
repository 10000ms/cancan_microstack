from aioclock import Every

from linglong_web import (
    BaseScheduler,
    to_group,
)
from cancan_microstack.services.infrasrv.interface.schedule.health_check import health_check_task
from cancan_microstack.services.infrasrv.interface.schedule.cleanup import cleanup_dead_instances_task
from cancan_microstack.services.infrasrv.interface.schedule.log_cleanup import cleanup_expired_logs_task
from cancan_microstack.services.infrasrv.interface.schedule.workflow_scheduler import workflow_scheduler_task
from cancan_microstack.services.infrasrv.interface.schedule.operation_tracker import operation_tracker_task

scheduler_group = to_group([
    BaseScheduler(
        name="service_health_check",
        trigger=Every(seconds=30, first_run_strategy="wait"),
        func=health_check_task,
    ),
    BaseScheduler(
        name="operation_tracker",
        trigger=Every(seconds=10, first_run_strategy="wait"),
        func=operation_tracker_task,
    ),
    BaseScheduler(
        name="cleanup_dead_instances",
        trigger=Every(minutes=5, first_run_strategy="wait"),
        func=cleanup_dead_instances_task,
    ),
    BaseScheduler(
        name="cleanup_log_documents",
        trigger=Every(hours=24, first_run_strategy="immediate"),
        func=cleanup_expired_logs_task,
    ),
    BaseScheduler(
        name="workflow_scheduler",
        trigger=Every(minutes=1, first_run_strategy="immediate"),
        func=workflow_scheduler_task,
    ),
])

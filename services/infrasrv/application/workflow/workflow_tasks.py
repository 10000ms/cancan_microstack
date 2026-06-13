"""Workflow Celery task registration helpers.

按照项目规范集中注册 Celery 任务，便于在 cmd/infrasrv/run.py 中一眼看出
服务暴露了哪些任务；同时也避免循环导入。
This module centralizes Celery task declarations so run.py can register them
explicitly, making task discovery and testing easier.
"""
import asyncio
import threading

from celery import Celery

from linglong_web import Rmanager
from cancan_microstack.public.const.workflow_consts import WorkflowTask
from cancan_microstack.services.infrasrv.application.workflow.workflow_app import workflow_app
from cancan_microstack.services.infrasrv.interface.schedule.workflow_scheduler import scan_and_trigger_workflows

_TASKS_REGISTERED = False
_REGISTER_LOCK = threading.Lock()


def register_workflow_tasks() -> None:
    """注册工作流相关的 Celery 任务 / Register workflow Celery tasks only once."""
    global _TASKS_REGISTERED
    if _TASKS_REGISTERED:
        return

    # 双重检查锁，避免并发调用重复注册任务
    # Double-checked locking to keep concurrent registrations idempotent
    with _REGISTER_LOCK:
        if _TASKS_REGISTERED:
            return

        celery_app: Celery = Rmanager.CeleryApp

        @celery_app.task(name=WorkflowTask.EXECUTE_NODE, bind=True, max_retries=3, acks_late=True)
        def execute_node_task(self, run_id: str, node_id: str, loop_index: int = 1):
            """调用执行协调器 / Run the async node orchestrator inside Celery."""
            asyncio.run(workflow_app._execute_node_orchestrator(run_id, node_id, loop_index))

        @celery_app.task(name=WorkflowTask.SCAN_SCHEDULED, bind=True, autoretry_for=(Exception,), retry_backoff=True)
        def scan_scheduled_task(self):
            """周期扫描数据库查找待执行的工作流 / Periodically scan DB for due workflows."""
            asyncio.run(scan_and_trigger_workflows())

        _TASKS_REGISTERED = True

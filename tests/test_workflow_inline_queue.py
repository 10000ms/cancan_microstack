import asyncio
from unittest.mock import AsyncMock

import pytest

from cancan_microstack.services.infrasrv.application.workflow import workflow_queue


@pytest.mark.asyncio
async def test_enqueue_node_execution_runs_inline_when_celery_missing(monkeypatch):
    called = []

    async def dummy_orchestrator(run_id: str, node_id: str, loop_index: int) -> None:
        called.append((run_id, node_id, loop_index))

    # Override orchestrator and force Celery to be unavailable.
    workflow_queue.register_inline_orchestrator(dummy_orchestrator)
    monkeypatch.setattr(workflow_queue.Rmanager, "CeleryApp", None, raising=False)

    workflow_queue.enqueue_node_execution("run-1", "node-1", 1)

    # Ensure tasks get a chance to run.
    await asyncio.sleep(0)
    await workflow_queue.wait_for_inline_queue_idle()

    assert called == [("run-1", "node-1", 1)]


def test_inline_executor_applies_backpressure_when_queue_is_full(monkeypatch):
    """当队列满时应进入异步背压分支而不是丢任务。
    When queue is full, executor should schedule async backpressure instead of dropping jobs.
    """

    executor = workflow_queue._InlineFallbackExecutor(max_concurrency=1, queue_limit=1)

    class _FakeQueue:
        def put_nowait(self, job):
            raise asyncio.QueueFull()

        def qsize(self):
            return 1

    class _FakeLoop:
        def __init__(self):
            self.tasks = []

        def create_task(self, coro):
            self.tasks.append(coro)
            return None

    fake_loop = _FakeLoop()
    monkeypatch.setattr(executor, "_ensure_queue", lambda loop: _FakeQueue())
    monkeypatch.setattr(executor, "_enqueue_with_backpressure", AsyncMock())
    monkeypatch.setattr(workflow_queue.asyncio, "get_running_loop", lambda: fake_loop)

    executor.submit("run-bp", "node-bp", 9)

    assert len(fake_loop.tasks) == 1
    scheduled_coro = fake_loop.tasks[0]
    if hasattr(scheduled_coro, "close"):
        scheduled_coro.close()

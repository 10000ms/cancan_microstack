"""Workflow task dispatch helpers for Celery.

提供封装后的 Celery 调度工具，避免业务层到处硬编码 task 名称。
This module centralizes Celery helper functions so higher layers can enqueue work
without importing Celery primitives directly.
"""
import asyncio
import threading
import time
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    Dict,
    Optional,
    Tuple,
)

from linglong_web.utils import logger

from cancan_microstack.public.const.workflow_consts import WorkflowTask
from linglong_web import LinglongConfig
from linglong_web import Rmanager

_WORKER_STATUS = {
    "checked_at": 0.0,
    "has_worker": False,
}
_WORKER_STATUS_LOCK = threading.Lock()


def _missing_inline_orchestrator(run_id: str, node_id: str, loop_index: int) -> Awaitable[None]:
    """当未注册 orchestrator 时，给出明确错误。
    Raise a clear error when inline orchestrator hasn't been registered.
    """

    async def _raise() -> None:
        raise RuntimeError(
            "Workflow inline orchestrator is not registered. "
            "Ensure workflow_app registers it via register_inline_orchestrator()."
        )

    return _raise()


_INLINE_ORCHESTRATOR: Callable[[str, str, int], Awaitable[None]] = _missing_inline_orchestrator
_INLINE_ORCHESTRATOR_LOCK = threading.Lock()


def register_inline_orchestrator(func: Callable[[str, str, int], Awaitable[None]]) -> None:
    """注册工作流节点内联执行 orchestrator。
    Register workflow node inline orchestrator.

    Note:
        This avoids a circular import between workflow_app and workflow_queue.
    """

    if not callable(func):
        raise TypeError("Inline orchestrator must be callable")

    global _INLINE_ORCHESTRATOR
    with _INLINE_ORCHESTRATOR_LOCK:
        _INLINE_ORCHESTRATOR = func


def _get_inline_orchestrator() -> Callable[[str, str, int], Awaitable[None]]:
    with _INLINE_ORCHESTRATOR_LOCK:
        return _INLINE_ORCHESTRATOR


def _to_positive_int(value, default: int) -> int:
    """将配置值转换为正整数 / Ensure config-driven integers stay positive."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return default
    return candidate if candidate > 0 else default


@dataclass(slots=True)
class _InlineJob:
    """表示一次内联执行任务 / Represents a single inline execution request."""

    run_id: str
    node_id: str
    loop_index: int


class _InlineFallbackExecutor:
    """受限并发的内联执行器，防止 Celery 降级时无限制堆积。
    Bounded-concurrency inline executor that prevents unbounded fan-out when Celery is unavailable.
    """

    def __init__(self, *, max_concurrency: int, queue_limit: int) -> None:
        self._max_concurrency = max_concurrency
        self._queue_limit = queue_limit
        self._queues: Dict[int, asyncio.Queue[_InlineJob]] = {}

    async def _run_job(self, job: _InlineJob) -> None:
        orchestrator = _get_inline_orchestrator()
        await orchestrator(job.run_id, job.node_id, job.loop_index)

    async def _worker(self, queue: asyncio.Queue[_InlineJob], worker_idx: int) -> None:
        """后台 worker，串行消费队列任务 / Background worker that drains inline queue with bounded concurrency."""

        while True:
            job = await queue.get()
            try:
                await self._run_job(job)
            except Exception as exc:  # noqa: BLE001 - inline fallback必须兜底 / inline fallback must never crash the orchestrator
                logger.error(
                    "Inline workflow worker %s failed for run=%s node=%s: %s",
                    worker_idx,
                    job.run_id,
                    job.node_id,
                    exc,
                    exc_info=True,
                )
            finally:
                queue.task_done()

    async def _enqueue_with_backpressure(self, queue: asyncio.Queue[_InlineJob], job: _InlineJob) -> None:
        """等待队列空位，避免一次性放入过多任务 / Wait for free slot instead of flooding the loop."""

        await queue.put(job)

    def _ensure_queue(self, loop: asyncio.AbstractEventLoop) -> asyncio.Queue[_InlineJob]:
        """按事件循环初始化队列和 worker / Ensure queue + workers exist for the active loop."""

        loop_id = id(loop)
        queue = self._queues.get(loop_id)
        if queue:
            return queue

        queue = asyncio.Queue(maxsize=self._queue_limit)
        self._queues[loop_id] = queue

        for idx in range(self._max_concurrency):
            loop.create_task(
                self._worker(queue, idx + 1),
                name=f"workflow-inline-worker-{idx + 1}",
            )

        return queue

    def submit(self, run_id: str, node_id: str, loop_index: int) -> None:
        """投递内联执行任务，自动施加并发限流。
        Submit inline execution with bounded concurrency to keep fallback predictable.
        """

        job = _InlineJob(run_id=run_id, node_id=node_id, loop_index=loop_index)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "No running event loop detected while executing workflow node inline; creating a temporary loop",
            )
            asyncio.run(self._run_job(job))
            return

        queue = self._ensure_queue(loop)

        try:
            queue.put_nowait(job)
        except asyncio.QueueFull:
            logger.warning(
                "Inline workflow queue saturated (size=%s limit=%s); applying async backpressure",
                queue.qsize(),
                self._queue_limit,
            )
            loop.create_task(self._enqueue_with_backpressure(queue, job))

    async def wait_for_idle(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """等待队列清空（测试辅助） / Wait for inline queue to drain (useful for tests)."""

        target_loop = loop or asyncio.get_running_loop()
        queue = self._queues.get(id(target_loop))
        if not queue:
            return
        await queue.join()


_INLINE_EXECUTOR: Optional[_InlineFallbackExecutor] = None
_INLINE_EXECUTOR_CONFIG: Optional[Tuple[int, int]] = None
_INLINE_EXECUTOR_OVERRIDE: Optional[_InlineFallbackExecutor] = None
_INLINE_EXECUTOR_LOCK = threading.Lock()


def _read_inline_executor_config() -> Tuple[int, int]:
    """读取并规范化内联执行器配置 / Read + normalize inline executor config."""

    max_concurrency = _to_positive_int(LinglongConfig.WORKFLOW_INLINE_MAX_CONCURRENCY, 4)
    queue_limit_hint = max(max_concurrency * 4, 1024)
    queue_limit = _to_positive_int(LinglongConfig.WORKFLOW_INLINE_QUEUE_LIMIT, queue_limit_hint)
    queue_limit = max(queue_limit, max_concurrency)
    return max_concurrency, queue_limit


def _get_inline_executor() -> _InlineFallbackExecutor:
    """根据当前 Config 获取内联执行器，支持热更新。
    Resolve inline executor lazily so Config updates take effect without process restarts.
    """

    override = _INLINE_EXECUTOR_OVERRIDE
    if override is not None:
        return override

    global _INLINE_EXECUTOR, _INLINE_EXECUTOR_CONFIG
    with _INLINE_EXECUTOR_LOCK:
        desired = _read_inline_executor_config()
        if _INLINE_EXECUTOR and _INLINE_EXECUTOR_CONFIG == desired:
            return _INLINE_EXECUTOR

        max_concurrency, queue_limit = desired
        logger.info(
            "Rebuilding inline executor due to config change: concurrency=%s queue_limit=%s",
            max_concurrency,
            queue_limit,
        )
        _INLINE_EXECUTOR = _InlineFallbackExecutor(
            max_concurrency=max_concurrency,
            queue_limit=queue_limit,
        )
        _INLINE_EXECUTOR_CONFIG = desired
        return _INLINE_EXECUTOR


async def wait_for_inline_queue_idle() -> None:
    """等待内联队列清空（测试辅助） / Wait for inline queue to drain (test helper)."""

    executor = _get_inline_executor()
    await executor.wait_for_idle()


def _celery_has_workers(celery_app, cache_ttl: float = 15.0) -> bool:
    """检测 Celery worker 是否在线，避免任务无限排队。
    Check if at least one Celery worker is alive so we can decide whether to enqueue or run inline."""

    now = time.monotonic()
    with _WORKER_STATUS_LOCK:
        checked_at = _WORKER_STATUS["checked_at"]
        cached_result = _WORKER_STATUS["has_worker"]

    if now - checked_at < cache_ttl:
        return cached_result

    try:
        responses = celery_app.control.ping(timeout=1.0) or []
        has_worker = len(responses) > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to ping Celery workers: %s", exc)
        has_worker = False

    with _WORKER_STATUS_LOCK:
        _WORKER_STATUS["checked_at"] = now
        _WORKER_STATUS["has_worker"] = has_worker
    return has_worker


def _execute_inline_node(run_id: str, node_id: str, loop_index: int) -> None:
    """直接在当前进程执行节点，但通过队列控制瞬时并发。
    Execute node orchestrator inline while honoring bounded inline concurrency.
    """

    executor = _get_inline_executor()
    executor.submit(run_id, node_id, loop_index)


def enqueue_node_execution(run_id: str, node_id: str, loop_index: int) -> None:
    """将节点执行请求投递到 Celery 队列 / Send a node execution request to Celery."""

    celery_app = Rmanager.CeleryApp
    if not celery_app:
        logger.warning(
            "Celery is not initialized, executing workflow node inline: run=%s node=%s",
            run_id,
            node_id,
        )
        _execute_inline_node(run_id, node_id, loop_index)
        return

    if not _celery_has_workers(celery_app):
        logger.warning(
            "Celery has no active workers, executing workflow node inline: run=%s node=%s",
            run_id,
            node_id,
        )
        _execute_inline_node(run_id, node_id, loop_index)
        return

    try:
        celery_app.send_task(WorkflowTask.EXECUTE_NODE, args=(run_id, node_id, loop_index))
    except Exception as exc:  # noqa: BLE001 - we need to capture all Celery backend issues
        logger.error(
            "Failed to enqueue workflow node via Celery (run=%s node=%s). Falling back to inline execution. Error: %s",
            run_id,
            node_id,
            exc,
            exc_info=True,
        )
        _execute_inline_node(run_id, node_id, loop_index)

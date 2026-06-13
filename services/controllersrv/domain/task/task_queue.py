"""
任务队列管理

实现异步任务队列、流水号管理、任务状态追踪
"""
import asyncio
from typing import (
    Dict,
    Any,
    Optional,
    Set,
)
from datetime import (
    datetime,
    timedelta,
)

from linglong_web.utils import logger
from cancan_microstack.public.const.operation_consts import OperationStatus
from cancan_microstack.public.schemas.controllersrv.responses import TaskQueueStats
from cancan_microstack.services.controllersrv.conf.settings import ServiceSettings
from cancan_microstack.public.schemas.controllersrv.task_models import Task


class TaskQueue:
    """任务队列类（简化锁机制）"""

    def __init__(self):
        """初始化任务队列"""
        self._queue: asyncio.Queue = asyncio.Queue(
            maxsize=ServiceSettings.TASK_QUEUE_MAX_SIZE
        )
        self._tasks: Dict[str, Task] = {}  # 流水号 -> 任务
        self._active_serial_numbers: Set[str] = set()  # 活跃的流水号
        self._lock = asyncio.Lock()  # 锁，保护整个队列状态

        logger.info("TaskQueue initialized")

    async def enqueue(self, task: Task) -> bool:
        """
        任务入队
        
        Args:
            task: 任务对象
        
        Returns:
            是否成功入队
        """
        try:
            # 使用单一锁保护整个操作
            async with self._lock:
                # 检查流水号是否已存在
                if task.serial_number in self._active_serial_numbers:
                    logger.warning(f"Duplicate serial number: {task.serial_number}")
                    # 对重复流水号统一抛出 ValueError，便于上层捕获并返回明确错误
                    # Raise ValueError for duplicate serial numbers so upper layers can map it to a clear error
                    raise ValueError("Duplicate serial number")

                # 检查队列是否已满
                if self._queue.full():
                    logger.warning("Task queue is full")
                    return False

                # 添加到队列和活跃集合
                await self._queue.put(task)
                self._tasks[task.serial_number] = task
                self._active_serial_numbers.add(task.serial_number)

                logger.info(
                    f"Task enqueued: serial={task.serial_number}, "
                    f"operation={task.operation}, "
                    f"queue_size={self._queue.qsize()}"
                )

                return True
        except (ValueError, asyncio.QueueFull):
            # 重新抛出已知异常
            raise
        except Exception as e:
            logger.error(f"Unexpected error in enqueue: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error during enqueue: {e}")

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[Task]:
        """
        任务出队（阻塞式）
        
        Args:
            timeout: 超时时间（秒），None 表示永久等待
        
        Returns:
            任务对象，超时返回 None
        """
        # 不要在持锁状态下 await self._queue.get()：那样会一直占着 self._lock，
        # 把需要同一把锁的生产者（enqueue）饿死。asyncio.Queue 本身是协程安全的，
        # 这里只读取队列、不动 dict/set 记账，无需加锁。
        # Do NOT hold self._lock while awaiting self._queue.get(): that would block
        # producers (enqueue) which need the same lock, starving them. asyncio.Queue is
        # coroutine-safe on its own, and this path only reads the queue without touching
        # the dict/set bookkeeping, so no lock is needed.
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)

            logger.info(
                f"Task dequeued: serial={task.serial_number}, "
                f"remaining={self._queue.qsize()}"
            )
            return task
        except asyncio.TimeoutError:
            # 超时是正常情况，不需要记录为错误
            return None
        except asyncio.CancelledError:
            logger.warning("Task dequeue operation cancelled")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during dequeue: {e}", exc_info=True)
            return None

    async def get_task(self, serial_number: str) -> Optional[Task]:
        """
        获取任务信息
        
        Args:
            serial_number: 流水号
        
        Returns:
            任务对象，不存在返回 None
        """
        async with self._lock:
            return self._tasks.get(serial_number)

    async def update_task_status(
            self,
            serial_number: str,
            status: OperationStatus,
            result: Optional[Dict[str, Any]] = None,
            error: Optional[str] = None
    ):
        """
        更新任务状态
        
        Args:
            serial_number: 流水号
            status: 新状态
            result: 执行结果
            error: 错误信息
        """
        try:
            if not serial_number:
                logger.error("Serial number cannot be empty for status update")
                return

            if not isinstance(status, OperationStatus):
                logger.error(f"Invalid status type: {type(status)}")
                return

            # 使用单一锁保护整个操作
            async with self._lock:
                task = self._tasks.get(serial_number)
                if not task:
                    logger.warning(f"Task not found: {serial_number}")
                    return

                task.status = status
                if result:
                    task.result = result
                if error:
                    task.error = error

                # 如果任务已完成，从活跃集合中移除
                if task.is_finished():
                    if serial_number in self._active_serial_numbers:
                        self._active_serial_numbers.discard(serial_number)
                        logger.info(f"Task finished, serial number released: {serial_number}")
        except Exception as e:
            logger.error(f"Error updating task status for {serial_number}: {e}", exc_info=True)

    async def remove_task(self, serial_number: str):
        """
        移除任务（用于清理）
        
        Args:
            serial_number: 流水号
        """
        async with self._lock:
            if serial_number in self._tasks:
                del self._tasks[serial_number]
            if serial_number in self._active_serial_numbers:
                self._active_serial_numbers.discard(serial_number)
            logger.debug(f"Task removed: {serial_number}")

    async def cleanup_old_tasks(self):
        """
        清理过期的已完成任务
        
        保留时间：ServiceSettings.SERIAL_NUMBER_MAX_AGE
        """
        async with self._lock:
            now = datetime.now()
            max_age = timedelta(seconds=ServiceSettings.SERIAL_NUMBER_MAX_AGE)

            expired_serials = []
            for serial, task in self._tasks.items():
                if task.is_finished() and task.finished_at:
                    age = now - task.finished_at
                    if age > max_age:
                        expired_serials.append(serial)

            # 删除过期任务
            for serial in expired_serials:
                del self._tasks[serial]
                self._active_serial_numbers.discard(serial)

            if expired_serials:
                logger.info(f"Cleaned up {len(expired_serials)} expired tasks")

    async def get_queue_stats(self) -> TaskQueueStats:
        """
        获取队列统计信息
        
        Returns:
            统计信息字典
        """
        async with self._lock:
            total_tasks = len(self._tasks)
            status_counts = {}

            for task in self._tasks.values():
                status = task.status
                status_counts[status] = status_counts.get(status, 0) + 1

            return TaskQueueStats(
                queue_size=self._queue.qsize(),
                total_tasks=total_tasks,
                active_serial_numbers=len(self._active_serial_numbers),
                status_counts=status_counts,
                max_queue_size=ServiceSettings.TASK_QUEUE_MAX_SIZE,
            )

    async def list_tasks(
            self,
            status: Optional[OperationStatus] = None,
            limit: int = 100
    ) -> list:
        """
        列出任务
        
        Args:
            status: 过滤状态，None 表示所有状态
            limit: 最大返回数量
        
        Returns:
            任务列表
        """
        async with self._lock:
            tasks = list(self._tasks.values())

            # 过滤状态
            if status:
                tasks = [t for t in tasks if t.status == status]

            # 按创建时间倒序
            tasks.sort(key=lambda t: t.created_at, reverse=True)

            # 限制数量
            tasks = tasks[:limit]

            return [t.to_dict() for t in tasks]


# 全局任务队列实例
_global_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """获取全局任务队列实例（单例模式）"""
    global _global_task_queue
    if _global_task_queue is None:
        _global_task_queue = TaskQueue()
    return _global_task_queue


def reset_task_queue():
    """重置全局任务队列（主要用于测试）"""
    global _global_task_queue
    _global_task_queue = None
    logger.info("Global task queue reset")

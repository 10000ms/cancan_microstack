"""
任务执行 Worker

负责从队列中获取任务并执行，确保同一时间只有一个任务在执行
"""
import asyncio
from typing import (
    Dict,
    Any,
    Optional,
)
import traceback

from linglong_web.utils import logger
from cancan_microstack.public.const.operation_consts import (
    OperationStatus,
    OperationType,
)
from cancan_microstack.public.const.controllersrv_consts import (
    TimeoutKey,
)
from cancan_microstack.services.controllersrv.conf.settings import ServiceSettings
from cancan_microstack.services.controllersrv.domain.task.task_queue import (
    Task,
    get_task_queue,
)
from dragonfly_container.core import UnifiedExecutor


class TaskWorker:
    """
    任务执行 Worker（直接使用 Dragonfly Container UnifiedExecutor）
    
    单线程工作模式：
    1. 从队列中阻塞式获取任务（FIFO）
    2. 执行任务（有超时、重试机制）
    3. 更新任务状态
    4. 释放流水号
    5. 继续处理下一个任务
    
    特点：
    - 单个 Worker 确保同时只执行一个任务，不需要额外的锁机制
    - 任务执行有总超时限制，防止卡死
    - 支持重试机制
    - 自动清理过期任务
    - 直接使用 UnifiedExecutor 统一操作 Docker/Podman
    """

    def __init__(self, executor: UnifiedExecutor):
        """
        初始化 Worker
        
        Args:
            executor: Dragonfly Container UnifiedExecutor 实例
        """
        self.executor = executor
        self.task_queue = get_task_queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(f"TaskWorker initialized with UnifiedExecutor: engine={executor.api.engine_type}")

    async def start(self):
        """启动 Worker"""
        if self._running:
            logger.warning("TaskWorker is already running")
            return

        self._running = True

        # 启动主工作循环
        self._worker_task = asyncio.create_task(self._work_loop())

        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("TaskWorker started")

    async def stop(self):
        """停止 Worker（增强资源清理）"""
        if not self._running:
            logger.warning("TaskWorker is not running")
            return

        self._running = False

        # 取消工作任务
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=10)
            except asyncio.CancelledError:
                logger.info("Worker task cancelled successfully")
            except asyncio.TimeoutError:
                logger.warning("Worker task didn't cancel gracefully, forcing cancellation")
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(f"Error stopping worker task: {e}")

        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5)
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled successfully")
            except asyncio.TimeoutError:
                logger.warning("Cleanup task didn't cancel gracefully, forcing cancellation")
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(f"Error stopping cleanup task: {e}")

        # 确保执行器资源也被清理
        try:
            if hasattr(self.executor, 'cleanup'):
                await self.executor.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up executor: {e}")

        logger.info("TaskWorker stopped with all resources cleaned up")

    async def _work_loop(self):
        """
        主工作循环
        
        持续从队列中获取任务并执行
        """
        logger.info("TaskWorker work loop started")

        while self._running:
            try:
                # 从队列中获取任务（阻塞式，带超时）
                task = await self.task_queue.dequeue(
                    timeout=ServiceSettings.WORKER_POLL_INTERVAL
                )

                if task:
                    # 执行任务
                    await self._execute_task(task)

            except Exception as e:
                logger.error(f"Error in work loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # 出错后短暂休眠

        logger.info("TaskWorker work loop stopped")

    async def _cleanup_loop(self):
        """
        清理循环
        
        定期清理过期的已完成任务
        """
        logger.info("TaskWorker cleanup loop started")

        while self._running:
            try:
                await asyncio.sleep(ServiceSettings.SERIAL_NUMBER_CLEANUP_INTERVAL)

                if self._running:
                    await self.task_queue.cleanup_old_tasks()

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)

        logger.info("TaskWorker cleanup loop stopped")

    async def _execute_task(self, task: Task):
        """
        执行单个任务（增强错误传播机制）
        
        Args:
            task: 任务对象
        """
        logger.info(
            f"Executing task: serial={task.serial_number}, "
            f"operation={task.operation}, "
            f"services={task.service_names}"
        )

        # 标记为运行中
        task.mark_running()
        try:
            await self.task_queue.update_task_status(
                task.serial_number,
                OperationStatus.RUNNING
            )
        except Exception as e:
            logger.error(f"Failed to update task status to RUNNING: {e}", exc_info=True)
            # 即使状态更新失败，也继续执行任务

        try:
            # 使用 asyncio.wait_for 实现总超时控制
            result = await asyncio.wait_for(
                self._execute_with_retry(task),
                timeout=ServiceSettings.TASK_MAX_EXECUTION_TIME
            )

            # 标记为成功
            task.mark_success(result)
            try:
                await self.task_queue.update_task_status(
                    task.serial_number,
                    OperationStatus.SUCCESS,
                    result=result
                )
            except Exception as e:
                logger.error(f"Failed to update task status to SUCCESS: {e}", exc_info=True)
                # 即使状态更新失败，也记录任务已完成

            logger.info(
                f"Task completed successfully: serial={task.serial_number}, "
                f"time={task.execution_time():.2f}s"
            )

        except asyncio.TimeoutError:
            # 总超时
            timeout_msg = f"Task execution timeout after {ServiceSettings.TASK_MAX_EXECUTION_TIME}s"
            task.mark_timeout()
            try:
                await self.task_queue.update_task_status(
                    task.serial_number,
                    OperationStatus.TIMEOUT,
                    error=timeout_msg
                )
            except Exception as update_error:
                logger.error(f"Failed to update task status to TIMEOUT: {update_error}", exc_info=True)

            logger.error(
                f"Task timeout: serial={task.serial_number}, "
                f"max_time={ServiceSettings.TASK_MAX_EXECUTION_TIME}s"
            )

        except Exception as e:
            # 执行失败 - 保留完整的错误信息和堆栈跟踪
            error_msg = str(e)
            error_traceback = traceback.format_exc()

            # 创建详细的错误信息
            detailed_error = {
                "message": error_msg,
                "traceback": error_traceback,
                "operation": task.operation,
                "services": task.service_names,
                "retry_count": task.retry_count
            }

            task.mark_failed(error_msg)
            try:
                await self.task_queue.update_task_status(
                    task.serial_number,
                    OperationStatus.FAILED,
                    error=error_msg,
                    result={"error_details": detailed_error}
                )
            except Exception as update_error:
                logger.error(f"Failed to update task status to FAILED: {update_error}", exc_info=True)

            logger.error(
                f"Task failed: serial={task.serial_number}, error={error_msg}",
                exc_info=True
            )

    async def _execute_with_retry(self, task: Task) -> Dict[str, Any]:
        """
        执行任务（带重试机制，增强错误传播）
        
        Args:
            task: 任务对象
        
        Returns:
            执行结果
        
        Raises:
            Exception: 所有重试失败后抛出异常，包含详细的错误信息
        """
        max_retries = ServiceSettings.MAX_RETRIES
        retry_delay = ServiceSettings.RETRY_DELAY
        last_error = None
        all_errors = []  # 记录所有尝试的错误

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Executing task (attempt {attempt}/{max_retries}): "
                    f"serial={task.serial_number}"
                )

                # 执行具体操作
                result = await self._execute_operation(task)

                # 成功，返回结果
                return result

            except Exception as e:
                last_error = e
                task.retry_count = attempt

                # 记录详细的错误信息
                error_info = {
                    "attempt": attempt,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "timestamp": asyncio.get_event_loop().time()
                }
                all_errors.append(error_info)

                logger.warning(
                    f"Task execution failed (attempt {attempt}/{max_retries}): "
                    f"serial={task.serial_number}, error={str(e)}"
                )

                # 如果还有重试机会，等待后重试
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        # 所有重试都失败，创建包含所有尝试信息的详细错误
        error_summary = {
            "total_attempts": max_retries,
            "last_error": str(last_error),
            "last_traceback": traceback.format_exc() if 'traceback' in locals() else "",
            "all_errors": all_errors,
            "operation": task.operation,
            "services": task.service_names
        }

        # 创建详细的错误消息
        detailed_error_msg = f"All {max_retries} attempts failed. Last error: {last_error}. All errors: {error_summary}"

        # 抛出包含所有错误信息的异常
        raise Exception(detailed_error_msg) from last_error

    async def _execute_operation(self, task: Task) -> Dict[str, Any]:
        """
        执行具体的操作
        
        Args:
            task: 任务对象
        
        Returns:
            执行结果
        """
        operation = task.operation
        service_names = task.service_names
        params = task.params

        # 根据操作类型构建命令（使用 UnifiedExecutor 的 get_*_command 方法）
        # Use UnifiedExecutor's get_*_command methods to build commands
        if operation == OperationType.START:
            cmd = self.executor.get_start_command(
                service_names=service_names,
                build=params.get("rebuild", False)
            )
            timeout = ServiceSettings.get_timeout(TimeoutKey.START)

        elif operation == OperationType.STOP:
            cmd = self.executor.get_stop_command(
                service_names=service_names
            )
            timeout = ServiceSettings.get_timeout(TimeoutKey.STOP)

        elif operation == OperationType.RESTART:
            cmd = self.executor.get_restart_command(
                service_names=service_names
            )
            timeout = ServiceSettings.get_timeout(TimeoutKey.RESTART)

        else:
            raise ValueError(f"Unsupported operation: {operation}")

        # 执行命令
        result = await self._run_command(cmd, timeout, str(operation))

        return result

    async def _run_command(
            self,
            cmd: list,
            timeout: int,
            operation_name: str
    ) -> Dict[str, Any]:
        """
        执行 shell 命令（增强资源清理）
        
        Args:
            cmd: 命令列表
            timeout: 超时时间（秒）
            operation_name: 操作名称（用于日志）
        
        Returns:
            执行结果
        
        Raises:
            Exception: 命令执行失败
        """
        logger.info(f"Running command [{operation_name}]: {' '.join(cmd)}")
        process = None

        try:
            # 使用 asyncio.create_subprocess_exec 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 等待命令完成（带超时）
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # 超时，强制终止进程及其子进程
                logger.warning(f"Command timeout after {timeout}s, terminating process group")
                try:
                    # 尝试优雅终止进程组
                    if hasattr(process, 'terminate'):
                        process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        # 如果优雅终止失败，强制杀死
                        logger.warning(f"Process didn't terminate gracefully, killing")
                        process.kill()
                        await process.wait()
                except Exception as cleanup_error:
                    logger.error(f"Error during process cleanup: {cleanup_error}")
                    # 确保进程被杀死
                    try:
                        process.kill()
                        await process.wait()
                    except:
                        pass  # 忽略清理过程中的错误

                raise Exception(f"Command timeout after {timeout}s")

            # 检查返回码
            if process.returncode != 0:
                error_output = stderr.decode('utf-8', errors='ignore').strip()
                raise Exception(
                    f"Command failed with code {process.returncode}: {error_output}"
                )

            # 成功
            output = stdout.decode('utf-8', errors='ignore').strip()
            logger.info(f"Command succeeded [{operation_name}]")

            return {
                "success": True,
                "output": output,
                "returncode": process.returncode,
            }

        except Exception as e:
            logger.error(f"Command failed [{operation_name}]: {e}")
            # 确保在异常情况下也清理进程
            if process:
                try:
                    if process.returncode is None:  # 进程仍在运行
                        process.kill()
                        await process.wait()
                except Exception as cleanup_error:
                    logger.error(f"Error during exception cleanup: {cleanup_error}")
            raise


# 全局 Worker 实例
_global_worker: Optional[TaskWorker] = None


def get_task_worker() -> Optional[TaskWorker]:
    """获取全局 Worker 实例"""
    return _global_worker


def set_task_worker(worker: TaskWorker):
    """设置全局 Worker 实例"""
    global _global_worker
    _global_worker = worker


def reset_task_worker():
    """重置全局 Worker 实例（主要用于测试）"""
    global _global_worker
    _global_worker = None
    logger.info("Global task worker reset")

"""
预注册钩子 (Pre-registration Hooks) 机制

提供服务注册前的钩子处理功能，允许在服务注册核心逻辑执行前，
动态地插入自定义的、可插拔的业务逻辑单元。
这是实现业务逻辑与核心流程解耦的关键。
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import (
    Dict,
    List,
    Optional,
    Callable,
)
from functools import wraps
import inspect

from cancan_microstack.public.schemas.infra.enums import (
    HookExecutionResult as HookResult,
    HookPriority,
)
from cancan_microstack.public.schemas.hooks import (
    HookContext,
    HookExecutionResult,
)
from linglong_web.utils import logger
from .hooks_log_utils import (
    log_hook_registration,
    log_hook_deregistration,
    log_hook_execution_start,
    log_hook_execution_success,
    log_hook_execution_failure,
    log_hook_rejection,
)
from .metrics import get_metrics_collector


class BaseHook(ABC):
    """
    钩子基类 (Abstract TableBase Class)。

    定义了所有具体 Hook 实现必须遵守的接口协定。
    这是一种策略模式（Strategy Pattern）的体现，每个 Hook 都是一个可替换的策略。
    """

    def __init__(self, name: str, priority: HookPriority = HookPriority.NORMAL):
        """
        初始化一个 Hook 实例。

        :param name: Hook 的唯一名称，用于识别和日志记录。
        :param priority: Hook 的执行优先级。值越小，优先级越高。
        """
        self.name = name
        self.priority = priority

    @abstractmethod
    async def execute(self, context: HookContext) -> HookExecutionResult:
        """
        执行钩子的核心逻辑。

        这是一个异步的抽象方法，所有子类都必须实现此方法。
        它接收一个 HookContext 对象，其中包含了执行决策所需的所有信息。

        :param context: 钩子执行的上下文信息。
        :return: 钩子执行的结果。
        """
        pass

    def __str__(self):
        return f"{self.__class__.__name__}(name={self.name}, priority={self.priority.name})"


class FunctionHook(BaseHook):
    """
    函数钩子 (Function-based Hook)。

    将一个普通的 Python 函数（同步或异步）包装成一个符合 BaseHook 接口的对象。
    这使得开发者可以简单地通过编写一个函数来定义一个 Hook 的逻辑。
    """

    def __init__(self, name: str, func: Callable, priority: HookPriority = HookPriority.NORMAL):
        super().__init__(name, priority)
        self.func = func  # 被包装的函数

    async def execute(self, context: HookContext) -> HookExecutionResult:
        """
        执行被包装的函数，并处理其返回结果。
        """
        start_time = datetime.now()
        error = None
        result = HookResult.SUCCESS
        message = ""

        try:
            # 优雅地处理同步和异步函数
            if inspect.iscoroutinefunction(self.func):
                # 如果是协程函数 (async def)，直接 await 调用
                hook_result = await self.func(context)
            else:
                # 如果是普通同步函数 (def)，在线程池中执行以避免阻塞事件循环
                loop = asyncio.get_event_loop()
                hook_result = await loop.run_in_executor(None, self.func, context)

            # 对被包装函数的返回值进行标准化处理，转换为 HookExecutionResult
            if isinstance(hook_result, HookResult):
                result = hook_result
                message = f"Hook {self.name} executed with result: {result.value}"
            elif isinstance(hook_result, bool):
                result = HookResult.SUCCESS if hook_result else HookResult.FAILURE
                message = f"Hook {self.name} returned: {hook_result}"
            elif isinstance(hook_result, tuple) and len(hook_result) == 2:
                result, message = hook_result
                if not isinstance(result, HookResult):
                    result = HookResult.SUCCESS if result else HookResult.FAILURE
            else:
                message = f"Hook {self.name} returned: {hook_result}"

        except Exception as e:
            # 捕获执行过程中的任何异常，并将其转化为一个 FAILURE 结果
            error = f"{type(e).__name__}: {str(e)}"
            result = HookResult.FAILURE
            message = f"Hook {self.name} failed: {error}"
            logger.error(f"Error executing hook {self.name}: {e}")

        execution_time = (datetime.now() - start_time).total_seconds()

        # 返回一个标准的、结构化的执行结果对象
        return HookExecutionResult(
            hook_name=self.name,
            result=result,
            message=message,
            execution_time=execution_time,
            error=error
        )


class HookManager:
    """
    钩子管理器 (Hook Manager)。

    作为整个 Hook 机制的中心调度器，负责 Hook 的注册、发现、组织和执行。
    """

    def __init__(self):
        # 按 service_type 存储的钩子，实现差异化流程
        self._hooks: Dict[str, List[BaseHook]] = {}
        # 全局钩子，对所有 service_type 都生效
        self._global_hooks: List[BaseHook] = []
        # 存储最近的 Hook 执行历史，用于调试和监控
        self._execution_history: List[HookExecutionResult] = []
        self._max_history = 1000  # 最大历史记录条数
        # 指标收集器，用于 Prometheus/Grafana 等监控系统
        self._metrics_collector = get_metrics_collector()

    def register_hook(self, hook: BaseHook, service_type: Optional[str] = None):
        """
        注册一个 Hook。

        可以将 Hook 注册为全局的，或针对特定的 service_type。
        注册后会根据优先级进行排序。

        :param hook: 要注册的 Hook 实例。
        :param service_type: 如果提供，则该 Hook 只对指定类型的服务生效。
        """
        if service_type:
            # 注册针对特定 service_type 的 Hook
            if service_type not in self._hooks:
                self._hooks[service_type] = []
            self._hooks[service_type].append(hook)
            # 根据优先级排序，值越小优先级越高
            self._hooks[service_type].sort(key=lambda h: h.priority.value)
            logger.info(f"Registered hook {hook.name} for service type {service_type}")

            self._metrics_collector.update_active_hooks_count(service_type, len(self._hooks[service_type]))
            log_hook_registration(logger, hook.name, service_type)
        else:
            # 注册全局 Hook
            self._global_hooks.append(hook)
            self._global_hooks.sort(key=lambda h: h.priority.value)
            logger.info(f"Registered global hook {hook.name}")

            self._metrics_collector.update_active_hooks_count("global", len(self._global_hooks))
            log_hook_registration(logger, hook.name, "global")

    def unregister_hook(self, hook_name: str, service_type: Optional[str] = None):
        """
        注销一个 Hook。

        :param hook_name: 要注销的 Hook 的名称。
        :param service_type: 如果提供，则只注销指定 service_type 下的同名 Hook。
        """
        if service_type and service_type in self._hooks:
            self._hooks[service_type] = [h for h in self._hooks[service_type] if h.name != hook_name]
            logger.info(f"Unregistered hook {hook_name} for service type {service_type}")
            self._metrics_collector.update_active_hooks_count(service_type, len(self._hooks[service_type]))
            log_hook_deregistration(logger, hook_name, service_type)
        else:
            self._global_hooks = [h for h in self._global_hooks if h.name != hook_name]
            logger.info(f"Unregistered global hook {hook_name}")
            self._metrics_collector.update_active_hooks_count("global", len(self._global_hooks))
            log_hook_deregistration(logger, hook_name, "global")

    def get_hooks(self, service_type: Optional[str] = None) -> List[BaseHook]:
        """
        根据 service_type 获取将要执行的 Hook 列表。

        返回的列表是全局 Hooks 和特定类型 Hooks 的并集，并已按优先级排序。

        :param service_type: 服务的类型。
        :return: 一个有序的 Hook 列表。
        """
        hooks = self._global_hooks.copy()
        if service_type and service_type in self._hooks:
            hooks.extend(self._hooks[service_type])
            hooks.sort(key=lambda h: h.priority.value)
        return hooks

    async def execute_hooks(self, context: HookContext) -> List[HookExecutionResult]:
        """
        执行与给定上下文匹配的所有 Hooks。

        这是 Hook 机制的核心调度方法。它负责：
        1. 筛选合适的 Hooks。
        2. 按顺序执行它们。
        3. 处理每个 Hook 的返回结果，包括重试、中断和超时。
        4. 记录详细的日志和监控指标。

        :param context: 本次执行的上下文。
        :return: 所有已执行的 Hooks 的结果列表。
        """
        hooks = self.get_hooks(context.service_type)
        results = []

        for hook in hooks:
            retry_count = 0
            max_retries = context.max_retries

            while retry_count <= max_retries:
                try:
                    # 为每个 Hook 创建独立的上下文副本，防止互相污染
                    hook_context = HookContext(
                        service_name=context.service_name,
                        service_type=context.service_type,
                        instance_id=context.instance_id,
                        host=context.host,
                        port=context.port,
                        metadata=context.metadata.copy(),
                        created_at=context.created_at,
                        retry_count=retry_count,
                        max_retries=max_retries,
                        timeout=context.timeout,
                        dry_run=context.dry_run
                    )

                    log_hook_execution_start(logger, hook.name, context.service_type, hook_context.metadata)

                    # 使用 asyncio.wait_for 实现单个 Hook 的超时控制
                    result = await asyncio.wait_for(
                        hook.execute(hook_context),
                        timeout=context.timeout
                    )

                    result.retry_count = retry_count

                    # 如果 Hook 成功执行并修改了元数据，将变更合并回主上下文
                    if result.result == HookResult.SUCCESS:
                        context.metadata.update(hook_context.metadata)

                    results.append(result)
                    self._add_to_history(result)
                    self._metrics_collector.record_hook_execution(
                        hook.name,
                        context.service_type,
                        result.result == HookResult.SUCCESS,
                        result.execution_time,
                        None if result.result == HookResult.SUCCESS else result.message
                    )

                    # 根据结果进行结构化日志记录
                    if result.result == HookResult.SUCCESS:
                        log_hook_execution_success(logger, hook.name, context.service_type, result.execution_time,
                                                   hook_context.metadata)
                    elif result.result == HookResult.FAILURE:
                        log_hook_execution_failure(logger, hook.name, context.service_type, result.execution_time,
                                                   result.message, hook_context.metadata)
                    elif result.result == HookResult.TERMINATE:
                        log_hook_rejection(logger, hook.name, context.service_type, result.message,
                                           hook_context.metadata)

                    # 核心流程控制逻辑
                    if result.result == HookResult.TERMINATE:
                        # 熔断机制：立即停止执行后续所有 Hooks
                        logger.warning(f"Hook {hook.name} terminated the execution chain")
                        return results
                    elif result.result == HookResult.FAILURE and retry_count >= max_retries:
                        logger.error(f"Hook {hook.name} failed after {max_retries} retries")
                        return results
                    elif result.result == HookResult.FAILURE:
                        # 失败重试
                        logger.warning(f"Hook {hook.name} failed, retrying ({retry_count + 1}/{max_retries})")
                        retry_count += 1
                        await asyncio.sleep(1)  # 重试前等待
                        continue
                    elif result.result == HookResult.RETRY:
                        # Hook 主动请求重试
                        logger.info(f"Hook {hook.name} requested retry ({retry_count + 1}/{max_retries})")
                        retry_count += 1
                        await asyncio.sleep(1)
                        continue
                    else:
                        # SUCCESS 或 SKIP，跳出重试循环，继续下一个 Hook
                        break

                except asyncio.TimeoutError:
                    # 超时处理
                    error_msg = f"Hook {hook.name} timed out after {context.timeout} seconds"
                    logger.error(error_msg)
                    result = HookExecutionResult(hook_name=hook.name, result=HookResult.FAILURE, message=error_msg,
                                                 retry_count=retry_count)
                    results.append(result)
                    self._add_to_history(result)
                    log_hook_execution_failure(logger, hook.name, context.service_type, 0, error_msg, context.metadata)
                    self._metrics_collector.record_hook_execution(hook.name, context.service_type, False, 0, error_msg)
                    retry_count += 1

                except Exception as e:
                    # 未知异常处理
                    error_msg = f"Unexpected error executing hook {hook.name}: {str(e)}"
                    logger.error(error_msg)
                    result = HookExecutionResult(hook_name=hook.name, result=HookResult.FAILURE, message=error_msg,
                                                 error=str(e), retry_count=retry_count)
                    results.append(result)
                    self._add_to_history(result)
                    log_hook_execution_failure(logger, hook.name, context.service_type, 0, error_msg, context.metadata,
                                               e)
                    self._metrics_collector.record_hook_execution(hook.name, context.service_type, False, 0, error_msg)
                    retry_count += 1

        return results

    def _add_to_history(self, result: HookExecutionResult):
        """添加执行结果到内存中的历史记录队列。"""
        self._execution_history.append(result)
        if len(self._execution_history) > self._max_history:
            self._execution_history.pop(0)

    def get_execution_history(self, service_name: Optional[str] = None,
                              hook_name: Optional[str] = None,
                              limit: int = 100) -> List[HookExecutionResult]:
        """获取 Hook 执行历史，用于 API 查询或调试。"""
        history = self._execution_history
        if service_name:
            pass
        if hook_name:
            history = [r for r in history if r.hook_name == hook_name]
        return history[-limit:] if limit > 0 else history

    def clear_history(self):
        """清空执行历史。"""
        self._execution_history.clear()
        logger.info("Cleared hook execution history")


def hook(name: Optional[str] = None, priority: HookPriority = HookPriority.NORMAL,
         service_type: Optional[str] = None):
    """
    Hook 装饰器。

    提供一种声明式的方式来创建和注册一个 FunctionHook。
    这是添加新 Hook 的首选方式，因为它非常简洁和直观。

    示例:
    @hook(name="my_validation_hook", priority=HookPriority.HIGH)
    def my_hook_logic(context: HookContext):
        # ...
    """

    def decorator(func: Callable):
        hook_name = name or f"{func.__module__}.{func.__name__}"
        function_hook = FunctionHook(hook_name, func, priority)

        # 导入并获取全局 HookManager 实例来注册自己
        from .hook_registry import get_hook_manager
        hook_manager = get_hook_manager()
        hook_manager.register_hook(function_hook, service_type)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 装饰器本身不改变原函数的行为
            return func(*args, **kwargs)

        return wrapper

    return decorator


# -------------------
# 预定义的、通用的 Hook 实现
# -------------------

class LoggingHook(BaseHook):
    """
    日志记录钩子。

    一个简单的示例 Hook，用于在执行链的开始记录一条日志。
    通常具有最高的优先级，以确保它总是第一个执行。
    """

    def __init__(self, name: str = "logging_hook", priority: HookPriority = HookPriority.HIGHEST):
        super().__init__(name, priority)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        logger.info(f"Executing pre-registration hook for service {context.service_name} "
                    f"(type: {context.service_type}, instance: {context.instance_id})")
        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message="Logged service registration"
        )


class ValidationHook(BaseHook):
    """
    验证钩子。

    用于执行基本的数据验证，确保传入的注册信息包含所有必要字段。
    """

    def __init__(self, name: str = "validation_hook", priority: HookPriority = HookPriority.HIGH):
        super().__init__(name, priority)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        if not context.service_name:
            return HookExecutionResult(hook_name=self.name, result=HookResult.FAILURE,
                                       message="Service name is required")
        if not context.service_type:
            return HookExecutionResult(hook_name=self.name, result=HookResult.FAILURE,
                                       message="Service type is required")
        if not context.instance_id:
            return HookExecutionResult(hook_name=self.name, result=HookResult.FAILURE,
                                       message="Instance ID is required")
        return HookExecutionResult(hook_name=self.name, result=HookResult.SUCCESS, message="Validation passed")


class MetadataHook(BaseHook):
    """
    元数据处理钩子。

    演示了 Hook 如何修改传入的上下文。
    这里它向服务的元数据中添加了注册时间戳和一个标记。
    """

    def __init__(self, name: str = "metadata_hook", priority: HookPriority = HookPriority.NORMAL):
        super().__init__(name, priority)

    async def execute(self, context: HookContext) -> HookExecutionResult:
        context.metadata["registered_at"] = datetime.now().isoformat()
        context.metadata["pre_hooks_executed"] = True
        return HookExecutionResult(
            hook_name=self.name,
            result=HookResult.SUCCESS,
            message="Metadata processed"
        )


# 模块自测试/示例代码
async def example_usage():
    """示例使用函数"""
    from .hook_registry import get_hook_manager
    from linglong_web.utils import logger
    hook_manager = get_hook_manager()
    hook_manager.register_hook(LoggingHook())
    hook_manager.register_hook(ValidationHook())
    hook_manager.register_hook(MetadataHook())
    context = HookContext(
        service_name="example-service",
        service_type="web",
        instance_id="example-123",
        metadata={"version": "1.0.0"}
    )
    results = await hook_manager.execute_hooks(context)
    for result in results:
        logger.info("%s: %s - %s", result.hook_name, result.result.value, result.message)


if __name__ == "__main__":
    asyncio.run(example_usage())

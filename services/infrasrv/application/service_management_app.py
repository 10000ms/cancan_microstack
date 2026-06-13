"""
服务管理应用层 / Service Management Application Layer

职责 / Responsibilities:
1. 统一管理所有 Docker 服务操作的生命周期 / Unified lifecycle management for all Docker service operations
2. 创建操作记录 → 调用 controllersrv → 更新操作状态 / Create operation record → Call controllersrv → Update operation status
3. 实现自动重试机制 / Implement automatic retry mechanism
4. 提供操作生命周期钩子（验证、通知、指标收集）/ Provide operation lifecycle hooks (validation, notification, metrics)
"""
import asyncio
from typing import (
    Dict,
    Any,
    Optional,
    Callable,
    List,
)
from datetime import (
    datetime,
    timezone,
)

from linglong_web.utils import logger

from cancan_microstack.services.infrasrv.infrastructure.api.controllersrv_api import ControllerSrvApi
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_action_log_op import (
    insert_service_action_log,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_operation_op import (
    create_operation,
    get_operation_by_id,
    update_operation,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_info_op import (
    update_expected_status,
)
from cancan_microstack.public.const.health_consts import ServiceRuntimeStatus
from cancan_microstack.public.schemas.infra.service_operation import (
    ServiceOperationCreate,
    ServiceOperation,
    ServiceOperationUpdate,
)
from cancan_microstack.public.schemas.infra.service_management import (
    ServiceManagementRequest,
    ServiceManagementResponse,
    HookResult,
    ControllerSrvResult,
)
from cancan_microstack.public.const.action_consts import ActionType
from cancan_microstack.public.const.operation_consts import (
    OperationType,
    OperationStatus,
    InitiatedBy,
    InitiatedFrom,
)


class ServiceManagementHooks:
    """
    服务管理操作钩子 / Service Management Operation Hooks
    
    提供可扩展的生命周期钩子系统 / Provides extensible lifecycle hook system
    """

    def __init__(self):
        # 预操作钩子列表（操作前执行：验证、准备）/ Pre-operation hooks (executed before operation: validation, preparation)
        self._pre_hooks: List[Callable] = []
        # 后操作钩子列表（操作后执行：通知、清理）/ Post-operation hooks (executed after operation: notification, cleanup)
        self._post_hooks: List[Callable] = []
        # 重试钩子列表（重试前执行：日志、延迟）/ Retry hooks (executed before retry: logging, delay)
        self._retry_hooks: List[Callable] = []

    def register_pre_hook(self, hook: Callable):
        """
        注册预操作钩子 / Register pre-operation hook
        
        钩子函数签名 / Hook function signature:
            async def hook(request: ServiceManagementRequest) -> HookResult
        
        返回值 / Return value:
            HookResult - 如果 allow=False，操作将被阻止 / If allow=False, operation will be blocked
        """
        self._pre_hooks.append(hook)
        logger.info(f"Registered pre-operation hook: {hook.__name__}")

    def register_post_hook(self, hook: Callable):
        """
        注册后操作钩子 / Register post-operation hook
        
        钩子函数签名 / Hook function signature:
            async def hook(request: ServiceManagementRequest, response: ServiceManagementResponse) -> None
        """
        self._post_hooks.append(hook)
        logger.info(f"Registered post-operation hook: {hook.__name__}")

    def register_retry_hook(self, hook: Callable):
        """
        注册重试钩子 / Register retry hook
        
        钩子函数签名 / Hook function signature:
            async def hook(request: ServiceManagementRequest, attempt: int, error: Exception) -> None
        """
        self._retry_hooks.append(hook)
        logger.info(f"Registered retry hook: {hook.__name__}")

    async def execute_pre_hooks(self, request: ServiceManagementRequest) -> HookResult:
        """
        执行所有预操作钩子 / Execute all pre-operation hooks
        
        Returns:
            HookResult - 钩子执行结果 / Hook execution result
        """
        for hook in self._pre_hooks:
            try:
                result = await hook(request)
                if not result.allow:
                    logger.warning(f"Pre-operation hook {hook.__name__} rejected operation: {result.reason}")
                    return result
            except Exception as e:
                logger.error(f"Pre-operation hook {hook.__name__} failed: {e}", exc_info=True)
                # 钩子失败不应阻止操作 / Hook failure should not block operation
        return HookResult(allow=True, reason="")

    async def execute_post_hooks(self, request: ServiceManagementRequest, response: ServiceManagementResponse):
        """执行所有后操作钩子 / Execute all post-operation hooks"""
        for hook in self._post_hooks:
            try:
                await hook(request, response)
            except Exception as e:
                logger.error(f"Post-operation hook {hook.__name__} failed: {e}", exc_info=True)

    async def execute_retry_hooks(self, request: ServiceManagementRequest, attempt: int, error: Exception):
        """执行所有重试钩子 / Execute all retry hooks"""
        for hook in self._retry_hooks:
            try:
                await hook(request, attempt, error)
            except Exception as e:
                logger.error(f"Retry hook {hook.__name__} failed: {e}", exc_info=True)


class ServiceManagementApp:
    """
    服务管理应用层 / Service Management Application Layer
    
    统一处理所有服务管理操作，作为 infrasrv 的核心控制平面 / Unified handling of all service management operations as infrasrv's core control plane
    """

    # 重试配置 / Retry Configuration
    MAX_RETRIES = 3  # 最大重试次数 / Maximum retry attempts
    RETRY_DELAY_SECONDS = 5  # 重试延迟（秒）/ Retry delay (seconds)
    RETRY_BACKOFF_MULTIPLIER = 2  # 退避倍数 / Backoff multiplier
    EXPECTED_STATUS_SYNC_TIMEOUT_SECONDS = 1.5
    EXPECTED_STATUS_SYNC_RETRIES = 3

    _OPERATION_EXPECTED_STATUS_MAP = {
        OperationType.START: ServiceRuntimeStatus.RUNNING.value,
        OperationType.RESTART: ServiceRuntimeStatus.RUNNING.value,
        OperationType.STOP: ServiceRuntimeStatus.STOPPED.value,
    }

    def __init__(self):
        self.controllersrv_api = ControllerSrvApi()
        self.hooks = ServiceManagementHooks()
        # 保存后台任务的强引用，防止 fire-and-forget 任务在运行期间被 GC 回收。
        # Hold strong references to background tasks so fire-and-forget tasks are not GC'd while running.
        self._bg: set = set()
        self._register_builtin_hooks()

    def _register_builtin_hooks(self):
        """注册内置钩子 / Register built-in hooks"""

        # 内置预操作钩子：参数验证 / Built-in pre-operation hook: parameter validation
        async def validate_request_hook(request: ServiceManagementRequest) -> HookResult:
            """验证请求参数 / Validate request parameters"""
            if not request.service_name:
                return HookResult(allow=False, reason="Service name is required")
            if not request.operation_id:
                return HookResult(allow=False, reason="Operation ID is required")
            return HookResult(allow=True, reason="")

        # 内置后操作钩子：指标收集 / Built-in post-operation hook: metrics collection
        async def metrics_collection_hook(request: ServiceManagementRequest, response: ServiceManagementResponse):
            """收集操作指标 / Collect operation metrics"""
            duration = None
            if response.started_at and response.completed_at:
                duration = (response.completed_at - response.started_at).total_seconds()

            logger.info(
                f"[Metrics] Operation completed: "
                f"type={request.operation_type}, "
                f"service={request.service_name}, "
                f"status={response.status}, "
                f"duration={duration}s"
            )

        # 内置重试钩子：日志记录 / Built-in retry hook: logging
        async def retry_logging_hook(request: ServiceManagementRequest, attempt: int, error: Exception):
            """记录重试信息 / Log retry information"""
            logger.warning(
                f"[Retry] Attempt {attempt}/{self.MAX_RETRIES} failed for operation {request.operation_id}: {error}"
            )

        self.hooks.register_pre_hook(validate_request_hook)
        self.hooks.register_post_hook(metrics_collection_hook)
        self.hooks.register_retry_hook(retry_logging_hook)

    async def execute_service_management(self, request: ServiceManagementRequest) -> ServiceManagementResponse:
        """
        执行服务管理操作（统一入口）/ Execute service management operation (unified entry point)
        
        流程 / Flow:
        1. 执行预操作钩子 / Execute pre-operation hooks
        2. 创建操作记录 / Create operation record
        3. 调用 controllersrv（带重试）/ Call controllersrv (with retry)
        4. 更新操作状态 / Update operation status
        5. 执行后操作钩子 / Execute post-operation hooks
        
        Args:
            request: 服务管理请求 / Service management request
        
        Returns:
            服务管理响应 / Service management response
        """
        logger.info(
            f"[ServiceManagementApp] Starting operation: "
            f"operation_id={request.operation_id}, "
            f"type={request.operation_type}, "
            f"service={request.service_name}"
        )

        # 步骤 1: 执行预操作钩子 / Step 1: Execute pre-operation hooks
        hook_result = await self.hooks.execute_pre_hooks(request)
        if not hook_result.allow:
            logger.warning(f"Operation {request.operation_id} rejected by pre-hooks: {hook_result.reason}")
            await self._record_action_log(
                request=request,
                action_status=OperationStatus.FAILED,
                stage="rejected_by_pre_hooks",
                error_message=hook_result.reason,
            )
            return ServiceManagementResponse(
                operation_id=request.operation_id,
                status=OperationStatus.FAILED,
                service_name=request.service_name,
                message=f"Operation rejected: {hook_result.reason}",
                error_message=hook_result.reason
            )

        # 步骤 2: 处理重复请求并创建操作记录 / Step 2: Handle duplicates and create operation record
        existing_operation = await get_operation_by_id(request.operation_id)
        if existing_operation:
            existing_status = self._coerce_operation_status(existing_operation.status)
            if existing_status != OperationStatus.PENDING or existing_operation.started_at:
                response = self._build_response_from_operation(
                    existing_operation,
                    default_message="Operation already exists",
                )
                await self._record_action_log(
                    request=request,
                    action_status=existing_status,
                    stage="duplicate_request",
                    error_message=response.error_message,
                )
                return response

            logger.info(
                "Operation record already exists and is pending: operation_id=%s",
                request.operation_id,
            )

        try:
            if not existing_operation:
                await self._create_operation_record(request)
            await self._record_action_log(
                request=request,
                action_status=OperationStatus.PENDING,
                stage="operation_record_created",
            )
        except Exception as e:
            logger.error(f"Failed to create operation record for {request.operation_id}: {e}", exc_info=True)
            await self._record_action_log(
                request=request,
                action_status=OperationStatus.FAILED,
                stage="operation_record_failed",
                error_message=str(e),
            )
            return ServiceManagementResponse(
                operation_id=request.operation_id,
                status=OperationStatus.FAILED,
                service_name=request.service_name,
                message=f"Failed to create operation record: {str(e)}",
                error_message=str(e)
            )

        # 步骤 3: 调用 controllersrv（带自动重试）/ Step 3: Call controllersrv (with automatic retry)
        started_at = datetime.now(timezone.utc)
        controller_result = await self._call_controllersrv_with_retry(request)
        controller_completed_at = datetime.now(timezone.utc)

        # 步骤 4: 更新操作状态 / Step 4: Update operation status
        if controller_result.success:
            status = OperationStatus.RUNNING
            error_message = None
            completed_at: Optional[datetime] = None
        else:
            status = OperationStatus.FAILED
            error_message = controller_result.error or "Unknown error from controllersrv"
            completed_at = controller_completed_at

        try:
            await self._update_operation_status(
                operation_id=request.operation_id,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                result=controller_result.model_dump(),
                error_message=error_message
            )
        except Exception as e:
            logger.error(f"Failed to update operation status for {request.operation_id}: {e}", exc_info=True)

        if controller_result.success:
            await self._sync_service_expected_status_with_timeout(request)

        # 构造响应 / Build response
        response = ServiceManagementResponse(
            operation_id=request.operation_id,
            status=status,
            service_name=request.service_name,
            message=controller_result.message or (
                "controllersrv accepted operation" if status == OperationStatus.RUNNING else "Operation failed"
            ),
            result=controller_result.model_dump(),
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at
        )

        await self._record_action_log(
            request=request,
            action_status=status,
            stage="operation_dispatched" if status == OperationStatus.RUNNING else "operation_failed",
            result=controller_result,
            error_message=error_message,
        )

        # 步骤 5: 执行后操作钩子 / Step 5: Execute post-operation hooks
        await self.hooks.execute_post_hooks(request, response)

        end_at = completed_at or controller_completed_at
        duration_seconds = None
        if started_at and end_at:
            duration_seconds = (end_at - started_at).total_seconds()

        duration_text = f"{duration_seconds:.2f}s" if duration_seconds is not None else "unknown"
        logger.info(
            f"[ServiceManagementApp] Operation completed: "
            f"operation_id={request.operation_id}, "
            f"status={status}, "
            f"duration={duration_text}"
        )

        return response

    async def _create_operation_record(self, request: ServiceManagementRequest) -> ServiceOperation:
        """创建操作记录 / Create operation record"""
        operation_data = ServiceOperationCreate(
            operation_id=request.operation_id,
            operation_type=request.operation_type,
            service_name=request.service_name,
            operation_params=request.operation_params,
            status=OperationStatus.PENDING,
            initiated_by=request.initiated_by,
            initiated_from=request.initiated_from,
        )
        operation = await create_operation(operation_data)
        logger.debug(f"Operation record created: {request.operation_id}")
        return operation

    @staticmethod
    def _coerce_operation_status(value: str) -> OperationStatus:
        """安全解析操作状态 / Safely parse operation status"""
        try:
            return OperationStatus(value)
        except ValueError:
            return OperationStatus.PENDING

    def _build_response_from_operation(
            self,
            operation: ServiceOperation,
            default_message: str,
    ) -> ServiceManagementResponse:
        """基于操作记录构造响应 / Build response from operation record"""
        status = self._coerce_operation_status(operation.status)
        message = default_message
        if isinstance(operation.result, dict):
            message = operation.result.get("message") or default_message

        return ServiceManagementResponse(
            operation_id=operation.operation_id,
            status=status,
            service_name=operation.service_name,
            message=message,
            result=operation.result or None,
            error_message=operation.error_message,
            started_at=operation.started_at,
            completed_at=operation.completed_at,
        )

    async def _update_operation_status(
            self,
            operation_id: str,
            status: OperationStatus,
            started_at: Optional[datetime] = None,
            completed_at: Optional[datetime] = None,
            result: Optional[Dict[str, Any]] = None,
            error_message: Optional[str] = None
    ):
        """更新操作状态 / Update operation status"""
        update_data = ServiceOperationUpdate(
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            result=result,
            error_message=error_message
        )
        await update_operation(operation_id, update_data)
        logger.debug(f"Operation status updated: {operation_id} -> {status}")

    async def _call_controllersrv_with_retry(self, request: ServiceManagementRequest) -> ControllerSrvResult:
        """
        调用 controllersrv 执行操作（带自动重试）/ Call controllersrv to execute operation (with automatic retry)
        
        实现指数退避重试策略 / Implements exponential backoff retry strategy
        
        Args:
            request: 服务管理请求 / Service management request
        
        Returns:
            ControllerSrvResult - 操作结果 / Operation result
        """
        last_error = None
        delay = self.RETRY_DELAY_SECONDS

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    f"[Retry Attempt {attempt}/{self.MAX_RETRIES}] Calling controllersrv for {request.operation_id}")
                result = await self._call_controllersrv(request)

                # 检查 controllersrv 是否成功接受任务 / Check if controllersrv successfully accepted the task
                if result.success:
                    logger.info(f"[Retry Success] Operation {request.operation_id} succeeded on attempt {attempt}")
                    return result
                else:
                    # controllersrv 拒绝任务（业务错误，不重试）/ controllersrv rejected task (business error, no retry)
                    logger.warning(f"[No Retry] Controllersrv rejected task {request.operation_id}: {result.error}")
                    return result  # 直接返回失败结果 / Return failure result directly

            except Exception as e:
                last_error = e
                logger.warning(f"[Retry Attempt {attempt}] Failed to call controllersrv: {e}")

            # 如果不是最后一次尝试，执行重试钩子并等待 / If not the last attempt, execute retry hooks and wait
            if attempt < self.MAX_RETRIES:
                await self.hooks.execute_retry_hooks(request, attempt, last_error)
                logger.info(f"[Retry] Waiting {delay}s before next attempt...")
                await asyncio.sleep(delay)
                delay *= self.RETRY_BACKOFF_MULTIPLIER  # 指数退避 / Exponential backoff

        # 所有重试失败 / All retries failed
        logger.error(f"[Retry Exhausted] All {self.MAX_RETRIES} attempts failed for {request.operation_id}")
        return ControllerSrvResult(
            success=False,
            error=f"All retry attempts exhausted. Last error: {str(last_error)}",
            retry_count=self.MAX_RETRIES
        )

    async def _sync_service_expected_status_with_timeout(self, request: ServiceManagementRequest) -> None:
        """
        以受控超时执行期望状态同步，避免阻塞主请求
        Sync expected_status with bounded timeout to avoid blocking API request
        """
        try:
            synced = await asyncio.wait_for(
                self._sync_service_expected_status(request),
                timeout=self.EXPECTED_STATUS_SYNC_TIMEOUT_SECONDS,
            )
            if not synced:
                retry_task = asyncio.create_task(self._sync_service_expected_status_retry(request))
                self._bg.add(retry_task)
                retry_task.add_done_callback(self._bg.discard)
        except asyncio.TimeoutError:
            logger.warning(
                "Expected_status sync timed out, scheduling async retry: service=%s, operation_id=%s",
                request.service_name,
                request.operation_id,
            )
            retry_task = asyncio.create_task(self._sync_service_expected_status_retry(request))
            self._bg.add(retry_task)
            retry_task.add_done_callback(self._bg.discard)

    async def _sync_service_expected_status_retry(self, request: ServiceManagementRequest) -> None:
        """
        后台重试同步期望状态
        Retry expected_status sync in background
        """
        for attempt in range(1, self.EXPECTED_STATUS_SYNC_RETRIES + 1):
            try:
                synced = await self._sync_service_expected_status(request)
                if synced:
                    return
            except Exception as exc:
                logger.warning(
                    "Async expected_status sync retry failed: service=%s, operation_id=%s, attempt=%s, error=%s",
                    request.service_name,
                    request.operation_id,
                    attempt,
                    exc,
                )

            if attempt < self.EXPECTED_STATUS_SYNC_RETRIES:
                await asyncio.sleep(float(attempt))

    async def _sync_service_expected_status(self, request: ServiceManagementRequest) -> bool:
        """
        根据操作类型同步服务期望状态
        Sync service expected_status based on accepted operation type
        """
        expected_status = self._OPERATION_EXPECTED_STATUS_MAP.get(request.operation_type)
        if not expected_status:
            return

        candidates = self._build_service_name_candidates(request.service_name)

        try:
            updated = None
            updated_service_name = None
            for candidate in candidates:
                updated = await update_expected_status(candidate, expected_status)
                if updated is not None:
                    updated_service_name = candidate
                    break

            if updated is None:
                logger.warning(
                    "Skip expected_status sync because service_info not found: service=%s, candidates=%s, expected_status=%s",
                    request.service_name,
                    candidates,
                    expected_status,
                )
                return False
            else:
                logger.info(
                    "Synced service expected_status: service=%s, matched_service=%s, expected_status=%s, operation_id=%s",
                    request.service_name,
                    updated_service_name,
                    expected_status,
                    request.operation_id,
                )
                return True
        except Exception as exc:
            logger.error(
                "Failed to sync expected_status: service=%s, operation_id=%s, error=%s",
                request.service_name,
                request.operation_id,
                exc,
                exc_info=True,
            )
            return False

    @staticmethod
    def _build_service_name_candidates(service_name: str) -> List[str]:
        """
        生成可能命中的服务名候选
        Build service name candidates for service_info lookup
        """
        base_name = service_name or ""
        candidates: List[str] = [base_name]

        if base_name.endswith(".service"):
            plain_name = base_name[:-len(".service")]
            if plain_name:
                candidates.append(plain_name)
        else:
            candidates.append(f"{base_name}.service")

        deduped: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in deduped:
                deduped.append(candidate)
        return deduped

    async def _call_controllersrv(self, request: ServiceManagementRequest) -> ControllerSrvResult:
        """
        调用 controllersrv 执行具体操作 / Call controllersrv to execute specific operation
        
        根据操作类型分派到不同的 API / Dispatch to different APIs based on operation type
        
        Args:
            request: 服务管理请求 / Service management request
        
        Returns:
            ControllerSrvResult - 操作结果 / Operation result
        """
        service_names = [request.service_name]
        operation_id = request.operation_id

        try:
            if request.operation_type == OperationType.START:
                return await self.controllersrv_api.start_services(service_names, operation_id)

            elif request.operation_type == OperationType.STOP:
                return await self.controllersrv_api.stop_services(service_names, operation_id)

            elif request.operation_type == OperationType.RESTART:
                return await self.controllersrv_api.restart_services(service_names, operation_id)
            else:
                raise ValueError(f"Unsupported operation type: {request.operation_type}")

        except Exception as e:
            logger.error(f"Exception when calling controllersrv for {operation_id}: {e}", exc_info=True)
            raise

    def _map_operation_type_to_action_type(self, operation_type: OperationType) -> ActionType:
        """根据操作类型映射日志行为类型 / Map operation type to action log type"""
        mapping = {
            OperationType.START: ActionType.START,
            OperationType.STOP: ActionType.STOP,
            OperationType.RESTART: ActionType.RESTART,
        }
        return mapping.get(operation_type, ActionType.RESTART)

    @staticmethod
    def _normalize_initiated_by(initiated_by: InitiatedBy) -> str:
        """规范化操作发起者字段 / Normalize initiated_by value"""
        if isinstance(initiated_by, InitiatedBy):
            return initiated_by
        return str(initiated_by)

    @staticmethod
    def _normalize_initiated_from(initiated_from: InitiatedFrom) -> str:
        """规范化操作来源字段 / Normalize initiated_from value"""
        if isinstance(initiated_from, InitiatedFrom):
            return initiated_from
        return str(initiated_from)

    async def _record_action_log(
            self,
            *,
            request: ServiceManagementRequest,
            action_status: OperationStatus,
            stage: str,
            result: Optional[ControllerSrvResult] = None,
            error_message: Optional[str] = None,
    ):
        """
        写入服务行为日志，确保所有管理操作可追踪
        Record service action logs so every management operation is traceable
        """
        action_type = self._map_operation_type_to_action_type(request.operation_type)
        metadata: Dict[str, Any] = {
            "operation_id": request.operation_id,
            "operation_stage": stage,
            "operation_params": request.operation_params,
            "initiated_from": self._normalize_initiated_from(request.initiated_from),
        }

        if result:
            metadata["controllersrv_result"] = result.model_dump()

        try:
            await insert_service_action_log(
                service_name=request.service_name,
                action_type=action_type,
                action_status=action_status,
                triggered_by=self._normalize_initiated_by(request.initiated_by),
                action_detail=result.model_dump() if result else None,
                error_message=error_message,
                action_metadata=metadata,
            )
        except Exception as exc:
            logger.error(
                "Failed to record action log for %s (stage=%s): %s",
                request.operation_id,
                stage,
                exc,
                exc_info=True,
            )

"""Service operation tracking logic.

该模块负责轮询 controllersrv 任务状态并同步到 PostgreSQL
This module polls controllersrv for task statuses and syncs results into PostgreSQL
"""
from datetime import (
    datetime,
    timezone,
)
from typing import Optional

from linglong_web.utils import logger

from cancan_microstack.public.const.operation_consts import OperationStatus, OperationType
from cancan_microstack.public.schemas.infra.service_operation import (
    ServiceOperation,
    ServiceOperationUpdate,
)
from cancan_microstack.public.schemas.controllersrv.responses import TaskStatusResponse
from cancan_microstack.public.schemas.infra.status_types import InstanceStatus
from cancan_microstack.services.infrasrv.infrastructure.api.controllersrv_api import ControllerSrvApi
from cancan_microstack.services.infrasrv.infrastructure.db.operate import service_operation_op
from cancan_microstack.services.infrasrv.domain.registry.service_registry import ServiceRegistry


class ServiceOperationTrackerApp:
    """服务操作跟踪器 / Service operation tracker"""

    # 只需要跟踪 pending/running 状态 / We only track pending or running operations
    _ACTIVE_STATUS_VALUES = (
        OperationStatus.PENDING,
        OperationStatus.RUNNING,
    )
    _FINAL_STATUSES = {
        OperationStatus.SUCCESS,
        OperationStatus.FAILED,
        OperationStatus.TIMEOUT,
        OperationStatus.CANCELLED,
    }
    _WINDOW_MINUTES = 10
    _POLL_BATCH_SIZE = 50

    _INSTANCE_FAST_OFFLINE_OPERATIONS = {
        OperationType.STOP,
        OperationType.RESTART,
    }

    def __init__(
            self,
            controller_api: Optional[ControllerSrvApi] = None,
            service_registry: Optional[ServiceRegistry] = None,
    ):
        self.controllersrv_api = controller_api or ControllerSrvApi()
        self.service_registry = service_registry or ServiceRegistry()

    async def run_once(self) -> None:
        """执行一次同步循环 / Run a single synchronization cycle"""

        await self._sync_active_operations()
        await self._timeout_stale_operations()

    async def _sync_active_operations(self) -> None:
        """查询 controllersrv 并刷新活跃操作状态 / Poll controllersrv for active operations"""

        operations = await service_operation_op.get_operations_for_polling(
            statuses=self._ACTIVE_STATUS_VALUES,
            max_age_minutes=self._WINDOW_MINUTES,
            limit=self._POLL_BATCH_SIZE,
        )

        if not operations:
            return

        for operation in operations:
            await self._sync_operation(operation)

    async def _sync_operation(self, operation: ServiceOperation) -> None:
        """同步单个操作的 controllersrv 状态 / Sync a single operation"""

        task_status: Optional[TaskStatusResponse] = await self.controllersrv_api.get_operation_status(
            operation.operation_id
        )
        if task_status is None:
            # controllersrv 没有返回任务信息 / controllersrv returned nothing
            logger.warning(
                "controllersrv did not return task for operation_id=%s",
                operation.operation_id,
            )
            return

        task_payload = task_status.task
        status_value = task_payload.get("status")
        if not status_value:
            logger.warning("Task payload missing status for %s", operation.operation_id)
            return

        try:
            mapped_status = OperationStatus(status_value)
        except ValueError:
            logger.warning("Unknown task status '%s' for %s", status_value, operation.operation_id)
            return

        update_payload = ServiceOperationUpdate(
            status=mapped_status,
            started_at=self._parse_datetime(task_payload.get("started_at")),
            result=task_payload.get("result"),
            error_message=task_payload.get("error"),
            retry_count=task_payload.get("retry_count"),
        )

        if mapped_status in self._FINAL_STATUSES:
            update_payload.completed_at = (
                    self._parse_datetime(task_payload.get("finished_at"))
                    or datetime.now(timezone.utc)
            )

        await service_operation_op.update_operation(operation.operation_id, update_payload)
        await self._handle_post_sync_cleanup(operation, mapped_status)

    async def _timeout_stale_operations(self) -> None:
        """将超时的操作标记为 timeout / Mark stale operations as timeout"""

        stale_operations = await service_operation_op.get_stale_operations(
            statuses=self._ACTIVE_STATUS_VALUES,
            older_than_minutes=self._WINDOW_MINUTES,
            limit=self._POLL_BATCH_SIZE,
        )

        if not stale_operations:
            return

        timeout_time = datetime.now(timezone.utc)
        for operation in stale_operations:
            await service_operation_op.update_operation(
                operation.operation_id,
                ServiceOperationUpdate(
                    status=OperationStatus.TIMEOUT,
                    completed_at=timeout_time,
                    error_message=(
                        "Operation exceeded 10 minutes without controllersrv completion"
                        " / 操作超过10分钟未完成，被标记为超时"
                    ),
                ),
            )

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """将 ISO 字符串解析为带时区的 datetime / Parse ISO string into aware datetime"""

        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            logger.warning("Failed to parse datetime value: %s", value)
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    async def _handle_post_sync_cleanup(
            self,
            operation: ServiceOperation,
            mapped_status: OperationStatus,
    ) -> None:
        """
        在获取 controllersrv 状态后执行额外清理逻辑
        Run extra cleanup logic after syncing controllersrv status
        """

        if mapped_status != OperationStatus.SUCCESS:
            return

        operation_type = self._parse_operation_type(operation.operation_type)
        if operation_type not in self._INSTANCE_FAST_OFFLINE_OPERATIONS:
            return

        instance_id = self._extract_instance_id(operation.operation_params)
        if not instance_id:
            return

        try:
            instance = await self.service_registry.get_instance(operation.service_name, instance_id)
        except Exception as exc:  # pragma: no cover - defensive logging for unexpected DB errors
            logger.error(
                "Failed to load instance for fast-offline cleanup: service=%s, instance=%s, error=%s",
                operation.service_name,
                instance_id,
                exc,
                exc_info=True,
            )
            return

        if not instance:
            logger.info(
                "Instance already absent during fast-offline cleanup: service=%s, instance=%s",
                operation.service_name,
                instance_id,
            )
            return

        if instance.status == InstanceStatus.DOWN:
            logger.debug(
                "Instance already marked DOWN, skip fast-offline cleanup: service=%s, instance=%s",
                operation.service_name,
                instance_id,
            )
            return

        try:
            await self.service_registry.deregister(operation.service_name, instance_id)
            logger.info(
                "Fast-offlined stopped instance after %s operation: service=%s, instance=%s",
                operation_type.value,
                operation.service_name,
                instance_id,
            )
        except Exception as exc:  # pragma: no cover - DB errors are logged for observability
            logger.error(
                "Failed to fast-offline instance after %s operation: service=%s, instance=%s, error=%s",
                operation_type.value,
                operation.service_name,
                instance_id,
                exc,
                exc_info=True,
            )

    @staticmethod
    def _extract_instance_id(params: Optional[dict]) -> Optional[str]:
        """从操作参数中提取实例ID / Extract instance_id from operation params"""

        if not isinstance(params, dict):
            return None

        instance_id = params.get("instance_id")
        if isinstance(instance_id, str):
            instance_id = instance_id.strip()
        return instance_id or None

    @staticmethod
    def _parse_operation_type(value: Optional[str]) -> Optional[OperationType]:
        """安全解析操作类型 / Safely parse operation type"""

        if not value:
            return None
        try:
            return OperationType(value)
        except ValueError:
            return None

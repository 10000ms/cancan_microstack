"""
健康检查领域层（升级版）

支持：
1. 多实例健康检查
2. 操作窗口期智能豁免
3. 区分正常/异常关闭
4. 失败处理策略（连续失败计数）
5. 自动调用 controllersrv 重启服务
"""
import asyncio
from typing import (
    Optional,
    Tuple,
)
from datetime import (
    datetime,
    timezone,
    timedelta,
)

from linglong_web.utils import logger
from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from linglong_web import LinglongConfig
from cancan_microstack.public.const.health_consts import InstanceHealthStatus
from cancan_microstack.public.schemas.infra.status_types import InstanceStatus
from cancan_microstack.public.const.operation_consts import (
    OperationStatus,
    InitiatedBy,
    InitiatedFrom,
)
from cancan_microstack.public.const.action_consts import HealthCheckAction
from cancan_microstack.public.schemas.infra.health_check import (
    InstanceHealthDetail,
    HealthCheckSummary,
)
from cancan_microstack.public.schemas.infra.service_instance import ServiceInstance
from cancan_microstack.public.schemas.infra.service_info import ServiceInfo
from cancan_microstack.public.schemas.infra.service_operation import ServiceOperation
from cancan_microstack.public.schemas.controllersrv.async_requests import (
    AsyncServiceOperationPayload,
    AsyncOperationParams,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_instance_op import (
    get_instances_by_status,
    update_instance_health_status,
    increment_instance_consecutive_failures,
    reset_instance_consecutive_failures,
    soft_delete_instance,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_info_op import (
    get_service_info_by_name,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_operation_op import (
    get_recent_operations_by_service,
)


class HealthCheckDomain:
    """
    健康检查领域层
    
    新增功能：
    - 支持多实例健康检查（遍历 service_instance_tbl）
    - 操作窗口期豁免（检查 service_operation_tbl 最近操作）
    - 区分正常/异常关闭（检查 service_info_tbl 的 expected_status）
    - 智能失败处理（连续失败计数、自动重启）
    """

    # 健康检查配置
    HEALTH_CHECK_TIMEOUT = 10.0  # 单次健康检查超时 10 秒
    HEALTH_CHECK_RETRY_COUNT = 2  # 失败后重试 2 次
    HEALTH_CHECK_RETRY_DELAY = 1.0  # 重试延迟 1 秒

    # 失败阈值
    CONSECUTIVE_FAILURE_THRESHOLD = 3  # 连续失败 3 次后标记为 unhealthy

    # 心跳超时
    HEARTBEAT_TIMEOUT_MINUTES = 5  # 5 分钟没有心跳认为不健康

    # 操作窗口期（豁免健康检查）
    OPERATION_WINDOW_MINUTES = 5  # 操作开始后 5 分钟内豁免健康检查

    def __init__(self):
        """初始化健康检查领域层"""
        self.controllersrv_host = LinglongConfig.CONTROLLERSRV_HOST if hasattr(LinglongConfig, 'CONTROLLERSRV_HOST') else "http://localhost:22100"
        # 保存后台任务的强引用，防止 fire-and-forget 任务在运行期间被 GC 回收。
        # Hold strong references to background tasks so fire-and-forget tasks are not GC'd while running.
        self._bg: set = set()
        logger.info("HealthCheckDomain initialized")

    async def health_check_all_instances(self) -> HealthCheckSummary:
        """
        对所有实例进行健康检查
        
        Returns:
            健康检查结果汇总
        """
        logger.info("Starting health check for all instances...")

        # 获取所有运行中的实例 (UP)
        all_instances = await get_instances_by_status(InstanceStatus.UP)

        check_results = HealthCheckSummary(total=len(all_instances))

        for instance in all_instances:
            detail = await self._check_single_instance(instance)

            # 统计结果
            if detail.exempted:
                check_results.exempted += 1
            elif detail.expected_stopped:
                check_results.expected_stopped += 1
            elif detail.health_status == InstanceHealthStatus.HEALTHY:
                check_results.healthy += 1
            elif detail.health_status == InstanceHealthStatus.DEGRADED:
                check_results.degraded += 1
            else:
                check_results.unhealthy += 1

            check_results.details.append(detail)

        logger.info(
            f"Health check completed: {check_results.healthy} healthy, "
            f"{check_results.degraded} degraded, {check_results.unhealthy} unhealthy, "
            f"{check_results.exempted} exempted, {check_results.expected_stopped} expected_stopped"
        )

        return check_results

    async def _check_single_instance(self, instance: ServiceInstance) -> InstanceHealthDetail:
        """
        检查单个实例的健康状态
        
        Args:
            instance: ServiceInstance 对象
        
        Returns:
            健康检查结果
        """
        instance_id = instance.instance_id
        service_name = instance.service_name

        # 准备初始字段，使用强类型字段
        health_status = InstanceHealthStatus.UNKNOWN
        consecutive_failures = instance.consecutive_failures or 0
        exempted = False
        exemption_reason = None
        expected_stopped = False
        action_taken: Optional[HealthCheckAction] = None
        last_heartbeat = instance.last_heartbeat.isoformat() if instance.last_heartbeat else None

        # 1. 检查是否在操作窗口期内（豁免检查）
        in_operation_window, operation_type = await self._is_in_operation_window(service_name)
        if in_operation_window:
            exempted = True
            exemption_reason = f"In operation window ({operation_type})"
            health_status = InstanceHealthStatus.EXEMPTED
            logger.debug(f"Instance {instance_id} exempted: {operation_type} operation in progress")
            return InstanceHealthDetail(
                instance_id=instance_id,
                service_name=service_name,
                host=instance.host,
                port=instance.port,
                status=instance.status,
                health_status=health_status,
                consecutive_failures=consecutive_failures,
                exempted=exempted,
                exemption_reason=exemption_reason,
                expected_stopped=expected_stopped,
                action_taken=action_taken,
                last_heartbeat=last_heartbeat,
            )

        # 2. 检查期望状态（区分正常/异常关闭）
        service_info: Optional[ServiceInfo] = await get_service_info_by_name(service_name)
        if service_info:
            expected_status = service_info.expected_status

            # 如果期望状态是 stopped (DOWN)，但实例还在运行，标记为异常
            if expected_status == InstanceStatus.DOWN:
                expected_stopped = True
                health_status = InstanceHealthStatus.EXPECTED_STOPPED
                logger.info(f"Instance {instance_id} expected to be stopped (expected_status=DOWN)")

                # 调用 controllersrv 停止该实例
                stop_task = asyncio.create_task(
                    self._auto_stop_instance(service_name, instance_id)
                )
                self._bg.add(stop_task)
                stop_task.add_done_callback(self._bg.discard)
                action_taken = HealthCheckAction.AUTO_STOP_SCHEDULED
                return InstanceHealthDetail(
                    instance_id=instance_id,
                    service_name=service_name,
                    host=instance.host,
                    port=instance.port,
                    status=instance.status,
                    health_status=health_status,
                    consecutive_failures=consecutive_failures,
                    exempted=exempted,
                    exemption_reason=exemption_reason,
                    expected_stopped=expected_stopped,
                    action_taken=action_taken,
                    last_heartbeat=last_heartbeat,
                )

        # 3. 执行实际的健康检查
        is_healthy = await self._perform_health_check_with_retry(instance)

        if is_healthy:
            # 健康检查成功
            health_status = InstanceHealthStatus.HEALTHY
            now_ts = datetime.now(timezone.utc)

            # 重置连续失败次数
            if instance.consecutive_failures > 0:
                await reset_instance_consecutive_failures(instance_id)
                logger.info(f"Instance {instance_id} recovered (previous failures: {instance.consecutive_failures})")

            # 更新健康状态和最后心跳
            await update_instance_health_status(
                instance_id=instance_id,
                health_status=InstanceHealthStatus.HEALTHY,
                last_health_check=now_ts,
                last_health_error=None,
                last_heartbeat=now_ts,
            )
            last_heartbeat = now_ts.isoformat()

        else:
            # 健康检查失败
            new_failure_count = await increment_instance_consecutive_failures(instance_id)
            
            # 如果实例不存在（可能已被清理），直接返回
            if new_failure_count is None:
                logger.warning(f"Instance {instance_id} not found when incrementing failure count")
                return InstanceHealthDetail(
                    instance_id=instance_id,
                    service_name=service_name,
                    host=instance.host,
                    port=instance.port,
                    status=instance.status,
                    health_status=InstanceHealthStatus.UNKNOWN,
                    consecutive_failures=consecutive_failures,
                    exempted=exempted,
                    exemption_reason="Instance Not Found",
                    expected_stopped=expected_stopped,
                    action_taken=action_taken,
                    last_heartbeat=last_heartbeat,
                )

            consecutive_failures = new_failure_count

            if new_failure_count >= self.CONSECUTIVE_FAILURE_THRESHOLD:
                # 达到失败阈值，标记为 unhealthy
                health_status = InstanceHealthStatus.UNHEALTHY

                await update_instance_health_status(
                    instance_id=instance_id,
                    health_status=InstanceHealthStatus.UNHEALTHY,
                    last_health_check=datetime.now(timezone.utc),
                    last_health_error=f"Failed {new_failure_count} consecutive health checks"
                )

                logger.error(
                    f"Instance {instance_id} marked as unhealthy "
                    f"after {new_failure_count} consecutive failures"
                )

                # 自动调用 controllersrv 重启实例
                restart_task = asyncio.create_task(
                    self._auto_restart_instance(service_name, instance_id)
                )
                self._bg.add(restart_task)
                restart_task.add_done_callback(self._bg.discard)
                action_taken = HealthCheckAction.AUTO_RESTART_SCHEDULED

            else:
                # 未达到阈值，标记为 degraded
                health_status = InstanceHealthStatus.DEGRADED

                await update_instance_health_status(
                    instance_id=instance_id,
                    health_status=InstanceHealthStatus.DEGRADED,
                    last_health_check=datetime.now(timezone.utc),
                    last_health_error=f"Failed {new_failure_count} health checks"
                )

                logger.warning(
                    f"Instance {instance_id} degraded "
                    f"({new_failure_count}/{self.CONSECUTIVE_FAILURE_THRESHOLD} failures)"
                )

        return InstanceHealthDetail(
            instance_id=instance_id,
            service_name=service_name,
            host=instance.host,
            port=instance.port,
            status=instance.status,
            health_status=health_status,
            consecutive_failures=consecutive_failures,
            exempted=exempted,
            exemption_reason=exemption_reason,
            expected_stopped=expected_stopped,
            action_taken=action_taken,
            last_heartbeat=last_heartbeat,
        )

    async def _is_in_operation_window(
            self,
            service_name: str,
            window_minutes: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        检查服务是否在操作窗口期内
        
        Args:
            service_name: 服务名称
            window_minutes: 窗口期时长（分钟），默认使用类常量
        
        Returns:
            (是否在窗口期, 操作类型)
        """
        if window_minutes is None:
            window_minutes = self.OPERATION_WINDOW_MINUTES

        # 查询最近的操作
        recent_operations: list[ServiceOperation] = await get_recent_operations_by_service(
            service_name=service_name,
            time_window_seconds=window_minutes * 60,
            status=OperationStatus.RUNNING  # 只检查正在运行的操作
        )

        if recent_operations:
            # 有正在运行的操作，豁免健康检查
            operation = recent_operations[0]
            operation_type = operation.operation_type
            logger.debug(
                f"Service {service_name} in operation window: {operation_type} "
                f"(started at {operation.created_time})"
            )
            return True, operation_type

        # 也检查最近完成的操作（5分钟内）
        completed_operations: list[ServiceOperation] = await get_recent_operations_by_service(
            service_name=service_name,
            time_window_seconds=window_minutes * 60,
            status=OperationStatus.SUCCESS
        )

        if completed_operations:
            operation = completed_operations[0]
            # 检查完成时间是否在窗口期内
            if operation.completed_at:
                now = datetime.now(timezone.utc)
                time_since_completion = now - operation.completed_at

                if time_since_completion < timedelta(minutes=window_minutes):
                    operation_type = operation.operation_type
                    logger.debug(
                        f"Service {service_name} in post-operation window: {operation_type} "
                        f"(completed {time_since_completion.total_seconds():.0f}s ago)"
                    )
                    return True, f"{operation_type} (completed)"

        return False, None

    async def _perform_health_check_with_retry(self, instance: ServiceInstance) -> bool:
        """
        执行健康检查（带重试）
        
        Args:
            instance: ServiceInstance 对象
        
        Returns:
            是否健康
        """
        # 1. 先检查心跳是否超时（超时不再立即返回，改为触发HTTP确认）
        if instance.last_heartbeat:
            now_utc = datetime.now(timezone.utc)
            last_heartbeat_utc = instance.last_heartbeat
            if last_heartbeat_utc.tzinfo is None:
                last_heartbeat_utc = last_heartbeat_utc.replace(tzinfo=timezone.utc)

            time_diff = now_utc - last_heartbeat_utc
            if time_diff > timedelta(minutes=self.HEARTBEAT_TIMEOUT_MINUTES):
                logger.warning(
                    f"Instance {instance.instance_id} heartbeat timeout: "
                    f"{time_diff.total_seconds():.0f}s (threshold: {self.HEARTBEAT_TIMEOUT_MINUTES * 60}s)"
                )
        else:
            logger.warning(
                f"Instance {instance.instance_id} has no heartbeat timestamp recorded; proceeding with HTTP check"
            )

        # 2. 尝试 HTTP 健康检查（带重试）
        for attempt in range(self.HEALTH_CHECK_RETRY_COUNT + 1):
            try:
                is_healthy = await self._perform_http_health_check(instance)

                if is_healthy:
                    if attempt > 0:
                        logger.info(
                            f"Instance {instance.instance_id} health check succeeded on retry {attempt}"
                        )
                    return True

                # 失败后重试
                if attempt < self.HEALTH_CHECK_RETRY_COUNT:
                    logger.debug(
                        f"Health check failed for {instance.instance_id}, "
                        f"retrying in {self.HEALTH_CHECK_RETRY_DELAY}s "
                        f"(attempt {attempt + 1}/{self.HEALTH_CHECK_RETRY_COUNT + 1})"
                    )
                    await asyncio.sleep(self.HEALTH_CHECK_RETRY_DELAY)

            except Exception as e:
                logger.error(
                    f"Health check error for {instance.instance_id} (attempt {attempt + 1}): {e}"
                )
                if attempt < self.HEALTH_CHECK_RETRY_COUNT:
                    await asyncio.sleep(self.HEALTH_CHECK_RETRY_DELAY)

        # 所有重试都失败
        return False

    async def _handle_instance_id_mismatch(self, instance: ServiceInstance, actual_instance_id: str) -> None:
        """处理实例 ID 不匹配的情况 / Handle stale registry records when IDs differ."""
        logger.warning(
            "Instance mismatch detected for service=%s host=%s:%s (record=%s, actual=%s). Marking stale record.",
            instance.service_name,
            instance.host,
            instance.port,
            instance.instance_id,
            actual_instance_id,
        )
        await soft_delete_instance(instance.service_name, instance.instance_id)

    async def _perform_http_health_check(self, instance: ServiceInstance) -> bool:
        """
        执行 HTTP 健康检查
        
        Args:
            instance: ServiceInstance 对象
        
        Returns:
            是否健康
        """
        try:
            health_url = f"http://{instance.host}:{instance.port}/internal/health"

            resp = await http_client.get(
                health_url,
                timeout=self.HEALTH_CHECK_TIMEOUT
            )

            if resp and resp.status == 200:
                actual_instance_id = None
                try:
                    body = await resp.json()
                    actual_instance_id = body.get("instance_id") if isinstance(body, dict) else None
                except Exception as parse_exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to decode health response for %s: %s", instance.instance_id, parse_exc
                    )

                if actual_instance_id and actual_instance_id != instance.instance_id:
                    await self._handle_instance_id_mismatch(instance, actual_instance_id)
                    return False

                return True
            else:
                logger.debug(
                    f"Health check failed for {instance.instance_id}: "
                    f"HTTP {resp.status if resp else 'None'}"
                )
                return False

        except asyncio.TimeoutError:
            logger.warning(f"Health check timeout for {instance.instance_id}")
            return False
        except Exception as e:
            logger.error(f"Health check exception for {instance.instance_id}: {e}")
            return False

    async def _auto_restart_instance(self, service_name: str, instance_id: str):
        """
        自动重启实例（调用 controllersrv）
        
        Args:
            service_name: 服务名称
            instance_id: 实例ID
        """
        try:
            logger.warning(f"Auto-restarting unhealthy instance: {instance_id}")

            # 调用 controllersrv 异步重启 API
            url = f"{self.controllersrv_host}/v1/controllersrv/async/service/restart"

            payload = AsyncServiceOperationPayload(
                service_name=f"{service_name}.service",
                operation_params=AsyncOperationParams(
                    instance_id=instance_id,
                    reason="auto_restart_unhealthy"
                ),
                initiated_by=InitiatedBy.INFRASRV_HEALTH_CHECK,
                initiated_from=InitiatedFrom.HEALTH_CHECK_DOMAIN
            )

            resp = await http_client.post(
                url,
                json=payload.model_dump(),
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )

            if resp and resp.status == 200:
                data = await resp.json()
                operation_id = data.get("data", {}).get("operation_id")
                logger.info(f"Auto-restart scheduled for {instance_id}, operation_id: {operation_id}")
            else:
                logger.error(
                    f"Failed to schedule auto-restart for {instance_id}: "
                    f"HTTP {resp.status if resp else 'None'}"
                )

        except Exception as e:
            logger.error(f"Error scheduling auto-restart for {instance_id}: {e}", exc_info=True)

    async def _auto_stop_instance(self, service_name: str, instance_id: str):
        """
        自动停止实例（调用 controllersrv）
        
        用于期望状态为 stopped 但实例还在运行的情况
        
        Args:
            service_name: 服务名称
            instance_id: 实例ID
        """
        try:
            logger.info(f"Auto-stopping instance (expected_status=stopped): {instance_id}")

            # 调用 controllersrv 异步停止 API
            url = f"{self.controllersrv_host}/v1/controllersrv/async/service/stop"

            payload = AsyncServiceOperationPayload(
                service_name=f"{service_name}.service",
                operation_params=AsyncOperationParams(
                    instance_id=instance_id,
                    reason="auto_stop_expected_stopped"
                ),
                initiated_by=InitiatedBy.INFRASRV_HEALTH_CHECK,
                initiated_from=InitiatedFrom.HEALTH_CHECK_DOMAIN
            )

            resp = await http_client.post(
                url,
                json=payload.model_dump(),
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )

            if resp and resp.status == 200:
                data = await resp.json()
                operation_id = data.get("data", {}).get("operation_id")
                logger.info(f"Auto-stop scheduled for {instance_id}, operation_id: {operation_id}")
            else:
                logger.error(
                    f"Failed to schedule auto-stop for {instance_id}: "
                    f"HTTP {resp.status if resp else 'None'}"
                )

        except Exception as e:
            logger.error(f"Error scheduling auto-stop for {instance_id}: {e}", exc_info=True)

import re
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from linglong_web.utils import logger
from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from linglong_web import LinglongConfig
from cancan_microstack.public.schemas.infra.service_registry import ServiceRegistryCreate
from cancan_microstack.public.schemas.infra.service_instance import ServiceInstance
from cancan_microstack.public.const.health_consts import HealthOverallStatus
from cancan_microstack.public.const.service_consts import PushStatus
from cancan_microstack.public.schemas.infra.status_types import InstanceStatus
from cancan_microstack.public.schemas.infra.push import PushResult, PushDetail
from cancan_microstack.public.const.action_consts import ActionType
from cancan_microstack.public.const.operation_consts import OperationStatus, InitiatedBy
from cancan_microstack.public.schemas.infra.overview import ServiceOverview
from cancan_microstack.public.schemas.infra.cleanup import CleanupResult, CleanupDetail
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_registry import (
    upsert_service_metadata,
    list_service_names,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_config import (
    get_service_config,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_action_log_op import (
    insert_service_action_log,
)
from cancan_microstack.services.infrasrv.infrastructure.db.operate.service_instance_op import (
    get_instance_by_id,
    list_instances_by_service,
    get_all_instances as list_all_instances,
    upsert_instance,
    soft_delete_instance,
    mark_instance_status,
    hard_delete_instances_by_ids,
)


class ServiceRegistry:
    """服务注册发现域"""

    _INVALID_HOSTS = {"unknown", "localhost", "127.0.0.1", "0.0.0.0"}
    _CONTAINER_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$", re.IGNORECASE)

    # 健康检查配置常量
    # Note: use HealthCheckDomain for multi-instance checks

    async def register(self, service: ServiceRegistryCreate) -> None:
        """
        注册服务实例
        
        验证规则：
        1. host 不能为 unknown（通常是 Docker 容器hostname 未正确设置）
        2. host 不能为空或纯空格
        3. 拒绝明显无效的服务名（infrasrv 等特殊服务）
        """
        normalized_host = self._normalize_instance_host(service)

        # 验证服务名
        if service.service_name in ("infrasrv", "controllersrv"):
            logger.warning(f"Reject registration: special service '{service.service_name}' should not register itself")
            raise ValueError(f"Special service '{service.service_name}' should not register")

        logger.info(
            "Registering service metadata and instance: %s (%s) @ %s",
            service.service_name,
            service.instance_id,
            normalized_host,
        )

        await upsert_service_metadata(service.to_service_metadata())
        await upsert_instance(self._build_instance_payload(service, normalized_host))

    @staticmethod
    def _is_local_dev_instance(service: ServiceRegistryCreate) -> bool:
        """
        判断实例是否来自容器外本地环境
        Determine whether the instance originates from out-of-pod local dev.
        """
        service_meta = service.service_metadata or {}
        instance_meta = service.instance_metadata or {}
        return bool(service_meta.get("is_local_dev") or instance_meta.get("is_local_dev"))

    @classmethod
    def _looks_like_container_hostname(cls, host: str) -> bool:
        """
        检测 host 是否为容器 ID
        Detect whether the host string is a container identifier.
        """
        return bool(cls._CONTAINER_ID_PATTERN.fullmatch(host.strip()))

    @staticmethod
    def _fallback_host_alias(service: ServiceRegistryCreate) -> Optional[str]:
        """
        生成可回退的网络别名（优先使用 compose/metadata 提供的值）
        Build the fallback alias (compose alias > metadata > service name).
        """
        instance_meta = service.instance_metadata or {}
        candidates = [
            instance_meta.get("network_alias"),
            service.compose_service_name,
            f"{service.service_name}.service",
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return None

    def _normalize_instance_host(self, service: ServiceRegistryCreate) -> str:
        """
        归一化实例 host，确保 infrasrv 可以回连
        Normalize the instance host so infrasrv can reach the service.
        """
        raw_host = (service.host or "").strip()
        is_local_dev = self._is_local_dev_instance(service)

        if not raw_host:
            fallback = self._fallback_host_alias(service)
            if fallback:
                logger.warning(
                    "Host missing for %s:%s, falling back to alias '%s'",
                    service.service_name,
                    service.instance_id,
                    fallback,
                )
                return fallback
            raise ValueError("Invalid host: host cannot be empty")

        lowered = raw_host.lower()
        if lowered in self._INVALID_HOSTS:
            if lowered == "127.0.0.1" and is_local_dev:
                return raw_host
            fallback = self._fallback_host_alias(service)
            if fallback:
                logger.info(
                    "Replacing invalid host '%s' with alias '%s' for %s:%s",
                    raw_host,
                    fallback,
                    service.service_name,
                    service.instance_id,
                )
                return fallback
            raise ValueError(
                f"Invalid host: '{raw_host}' is not routable. Configure SERVICE_NETWORK_ALIAS or hostname."
            )

        if self._looks_like_container_hostname(raw_host):
            fallback = self._fallback_host_alias(service)
            if fallback:
                logger.info(
                    "Replacing container hostname '%s' with alias '%s' for %s:%s",
                    raw_host,
                    fallback,
                    service.service_name,
                    service.instance_id,
                )
                return fallback
            logger.warning(
                "Host '%s' looks like a container ID but no alias found for %s:%s",
                raw_host,
                service.service_name,
                service.instance_id,
            )

        return raw_host

    def _build_instance_payload(self, service: ServiceRegistryCreate, normalized_host: str):
        """
        构造用于 upsert 的实例载荷，同时保存原始 host 信息
        Build the instance payload for persistence and keep host provenance.
        """
        payload = service.to_instance_payload()
        metadata = dict(payload.instance_metadata or {})
        metadata.setdefault("resolved_host", normalized_host)
        if service.host != normalized_host:
            metadata["reported_host"] = service.host
        return payload.model_copy(update={
            "host": normalized_host,
            "instance_metadata": metadata,
        })

    async def deregister(self, service_name: str, instance_id: str) -> None:
        """注销服务实例"""
        logger.info(f"Deregistering service: {service_name}, instance: {instance_id}")
        await mark_instance_status(service_name, instance_id, InstanceStatus.DOWN)
        await soft_delete_instance(service_name, instance_id)

    async def get_instances(self, service_name: str, only_healthy: bool = True) -> List[ServiceInstance]:
        """获取服务实例列表"""
        instances = await list_instances_by_service(service_name)
        if only_healthy:
            return [inst for inst in instances if inst.status == InstanceStatus.UP]
        return instances

    async def get_all_instances(self) -> List[ServiceInstance]:
        """获取所有服务实例"""
        return await list_all_instances()

    async def get_instance(self, service_name: str, instance_id: str) -> Optional[ServiceInstance]:
        """获取指定服务实例"""
        instance = await get_instance_by_id(instance_id)
        if instance and instance.service_name != service_name:
            return None
        return instance

    async def push_config_to_service(self, service_name: str) -> Dict[str, Any]:
        """向服务推送配置"""
        logger.info(f"Pushing config to service: {service_name}")

        # 获取服务配置
        config_dict = {}
        configs = await get_service_config(service_name)
        if configs:
            config_dict = {c.conf_key: c.conf_value for c in configs}

        # 获取健康的服务实例
        instances = await list_instances_by_service(service_name)
        instances = [inst for inst in instances if inst.status == InstanceStatus.UP]

        push_results = PushResult(service_name=service_name, total_instances=len(instances))

        for instance in instances:
            try:
                # 确定推送配置使用的host
                is_local_dev = False
                if instance.instance_metadata:
                    is_local_dev = instance.instance_metadata.get("is_local_dev", False)

                push_host = "127.0.0.1" if is_local_dev else instance.host

                url = f"http://{push_host}:{instance.port}/internal/config/update"

                resp = await http_client.post(url, json={"config": config_dict},
                                              timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT)

                if resp and resp.status == 200:
                    push_results.success += 1
                    push_results.details.append(
                        PushDetail(
                            instance_id=instance.instance_id,
                            host=instance.host,
                            port=instance.port,
                            status=PushStatus.SUCCESS,
                        )
                    )
                else:
                    push_results.failed += 1
                    push_results.details.append(
                        PushDetail(
                            instance_id=instance.instance_id,
                            host=instance.host,
                            port=instance.port,
                            status=PushStatus.FAILED,
                            error=f"HTTP {resp.status if resp else 'None'}",
                        )
                    )
                    # 推送配置失败，增加失败计数（不立即标记为DOWN）
                    logger.warning(
                        f"Failed to push config to {instance.service_name}:{instance.instance_id}, "
                        f"will be caught in next health check"
                    )
            except Exception as e:
                push_results.failed += 1
                push_results.details.append(
                    PushDetail(
                        instance_id=instance.instance_id,
                        host=instance.host,
                        port=instance.port,
                        status=PushStatus.FAILED,
                        error=str(e),
                    )
                )
                logger.error(f"Failed to push config to {instance.instance_id}: {e}")

        logger.info(f"Config push completed: {push_results.success} success, {push_results.failed} failed")
        return push_results.model_dump()

    async def get_all_service_names(self) -> List[str]:
        return await list_service_names()

    async def get_services_overview(self) -> List[Dict[str, Any]]:
        """获取所有服务的概览信息（服务名、状态统计）"""
        all_instances = await list_all_instances()

        # 使用结构化模型返回服务概览
        overview_map: Dict[str, ServiceOverview] = {}

        for instance in all_instances:
            service_name = instance.service_name
            if service_name not in overview_map:
                overview_map[service_name] = ServiceOverview(
                    service_name=service_name,
                    total_instances=0,
                    healthy_instances=0,
                    unhealthy_instances=0,
                    overall_status=HealthOverallStatus.UP,
                )

            ov = overview_map[service_name]
            ov.total_instances += 1
            # 尝试将实例状态转换为枚举以便比较，如果失败则回退为原始字符串
            try:
                inst_status = InstanceStatus(instance.status)
            except Exception:
                inst_status = instance.status

            if inst_status == InstanceStatus.UP:
                ov.healthy_instances += 1
            else:
                ov.unhealthy_instances += 1

        # 计算整体状态
        for service_name, ov in overview_map.items():
            if ov.healthy_instances == 0:
                ov.overall_status = HealthOverallStatus.DOWN
            elif ov.unhealthy_instances > 0:
                ov.overall_status = HealthOverallStatus.PARTIAL
            else:
                ov.overall_status = HealthOverallStatus.UP

        return [ov.model_dump() for ov in overview_map.values()]

    async def cleanup_dead_instances(self) -> Dict[str, Any]:
        """
        清理僵尸和已下线的服务实例
        Cleanup zombie and downed service instances.
        
        执行两个阶段的清理：
        1.  **标记僵尸实例**：将心跳超时的 `UP` 状态实例标记为 `DOWN` (软删除)。
        2.  **清理下线实例**：物理删除状态为 `DOWN` 且超过清理周期的实例。
        """
        logger.info("Starting cleanup/health-check of service instances...")
        all_instances = await list_all_instances()

        timeout_seconds = LinglongConfig.INSTANCE_HEARTBEAT_TIMEOUT_SECONDS
        cleanup_threshold = timedelta(seconds=timeout_seconds)
        current_time = datetime.now(timezone.utc)

        instances_to_soft_delete = []
        instances_to_hard_delete = []
        kept_count = 0

        for instance in all_instances:
            # --- 阶段1: 识别僵尸实例 ---
            if instance.status == InstanceStatus.UP:
                is_stale = False
                last_heartbeat = instance.last_heartbeat
                if last_heartbeat:
                    if last_heartbeat.tzinfo is None:
                        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
                    if (current_time - last_heartbeat) > cleanup_threshold:
                        is_stale = True
                else:
                    created_time = instance.created_time
                    if created_time:
                        if created_time.tzinfo is None:
                            created_time = created_time.replace(tzinfo=timezone.utc)
                        if (current_time - created_time) > cleanup_threshold:
                            is_stale = True

                if is_stale:
                    instances_to_soft_delete.append(instance)
                else:
                    kept_count += 1

            # --- 阶段2: 识别需要物理删除的实例 ---
            elif instance.status == InstanceStatus.DOWN:
                update_time = instance.update_time
                if update_time:
                    if update_time.tzinfo is None:
                        update_time = update_time.replace(tzinfo=timezone.utc)
                    if (current_time - update_time) > cleanup_threshold:
                        instances_to_hard_delete.append(instance)
                    else:
                        kept_count += 1
                else:
                    # 如果没有更新时间，默认保留
                    kept_count += 1
            else:
                kept_count += 1

        # --- 执行数据库操作 ---
        cleanup_results = CleanupResult(
            total_checked=len(all_instances),
            kept=kept_count
        )

        # 执行软删除
        for instance in instances_to_soft_delete:
            try:
                await soft_delete_instance(instance.service_name, instance.instance_id)
                cleanup_results.cleaned += 1
                cleanup_results.details.append(CleanupDetail(
                    service_name=instance.service_name,
                    instance_id=instance.instance_id,
                    action="soft_deleted",
                    reason="Stale heartbeat",
                ))
                logger.info(f"Soft deleted stale instance: {instance.service_name}:{instance.instance_id}")
            except Exception as e:
                logger.error(f"Failed to soft-delete instance {instance.instance_id}: {e}")

        # 执行物理删除
        if instances_to_hard_delete:
            instance_ids_to_delete = [inst.instance_id for inst in instances_to_hard_delete]
            try:
                deleted_count = await hard_delete_instances_by_ids(instance_ids_to_delete)
                cleanup_results.cleaned += deleted_count
                for inst in instances_to_hard_delete:
                    cleanup_results.details.append(CleanupDetail(
                        service_name=inst.service_name,
                        instance_id=inst.instance_id,
                        action="hard_deleted",
                        reason="Downed instance expired",
                    ))
                logger.info(f"Hard deleted {deleted_count} expired downed instances.")
            except Exception as e:
                logger.error(f"Failed to hard-delete instances: {e}")

        logger.info(
            f"Health check completed: {cleanup_results.cleaned} instances cleaned, "
            f"{cleanup_results.kept} instances kept."
        )
        return cleanup_results.model_dump()

    async def _auto_restart_service(self, service_name: str, instance_id: str):
        """
        自动重启失败的服务
        
        Args:
            service_name: 服务名称
            instance_id: 实例ID
        """
        try:
            # 记录日志：准备重启
            logger.info(f"Auto-restarting service {service_name}:{instance_id} via controllersrv")

            # 记录行为日志
            await insert_service_action_log(
                service_name=service_name,
                action_type=ActionType.AUTO_RESTART,
                action_status=OperationStatus.PENDING,
                triggered_by=InitiatedBy.INFRASRV,
                action_metadata={"instance_id": instance_id, "reason": "health_check_failure"}
            )

            # 调用 controllersrv 重启服务
            controllersrv_url = f"{LinglongConfig.CONTROLLERSRV_HOST}/v1/controllersrv/service/restart"
            resp = await http_client.post(
                url=controllersrv_url,
                json={"service_names": [service_name]},
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )

            if resp and resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    logger.info(f"Successfully triggered restart for service {service_name}")
                    await insert_service_action_log(
                        service_name=service_name,
                        action_type=ActionType.AUTO_RESTART,
                        action_status=OperationStatus.SUCCESS,
                        triggered_by=InitiatedBy.INFRASRV,
                        action_metadata={"instance_id": instance_id, "controllersrv_response": data}
                    )
                else:
                    error_msg = data.get("error", {}).get("msg", "Unknown error")
                    logger.error(f"Failed to restart service {service_name}: {error_msg}")
                    await insert_service_action_log(
                        service_name=service_name,
                        action_type=ActionType.AUTO_RESTART,
                        action_status=OperationStatus.FAILED,
                        triggered_by=InitiatedBy.INFRASRV,
                        error_message=error_msg,
                        action_metadata={"instance_id": instance_id}
                    )
            else:
                error_msg = f"HTTP error: {resp.status if resp else 'no response'}"
                logger.error(f"Failed to call controllersrv for {service_name}: {error_msg}")
                await insert_service_action_log(
                    service_name=service_name,
                    action_type=ActionType.AUTO_RESTART,
                    action_status=OperationStatus.FAILED,
                    triggered_by=InitiatedBy.INFRASRV,
                    error_message=error_msg,
                    action_metadata={"instance_id": instance_id}
                )
        except Exception as e:
            logger.error(f"Error auto-restarting service {service_name}: {e}", exc_info=True)
            await insert_service_action_log(
                service_name=service_name,
                action_type=ActionType.AUTO_RESTART,
                action_status=OperationStatus.FAILED,
                triggered_by=InitiatedBy.INFRASRV,
                error_message=str(e),
                action_metadata={"instance_id": instance_id}
            )

"""项目 AppServer，基于 Linglong 扩展服务注册、远程配置与内部管理路由。"""
import asyncio
import os
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Sequence,
    Tuple,
)

from fastapi import (
    APIRouter,
    Request,
)
from fastapi.responses import ORJSONResponse

from linglong_web import (
    LinglongConfig,
    LinglongConfigBase,
)
from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from linglong_web import LinglongAppServer
from linglong_web import BaseServerExtension
from linglong_web import LinglongConst
from linglong_web.utils import logger

from cancan_microstack.public.const.app_consts import WebServerConst
from cancan_microstack.public.schemas.service_registry import (
    InstanceMetadata,
    ServiceMetadata,
    ServiceRegistryPayload,
)
from cancan_microstack.public.schemas.infra.status_types import InstanceStatus
from cancan_microstack.public.web.config_value import ConfigValueResolver


class AppServer(LinglongAppServer):
    """项目 AppServer，实现服务注册、配置下发等行为 / Project specific AppServer."""

    def __init__(self) -> None:
        super().__init__()
        self._registry_keepalive_task: Optional[asyncio.Task] = None
        self._config_value_resolver = ConfigValueResolver()

    async def initialize(
            self,
            service_name: str,
            router: APIRouter,
            config_dict: Dict[str, type[LinglongConfigBase]],
            scheduler_group=None,
            middleware: Optional[list[Callable[[Request, Callable[[Request], Awaitable[Any]]], Awaitable[Any]]]] = None,
            on_startup: Optional[Sequence[Callable[[], Any]]] = None,
            on_shutdown: Optional[Sequence[Callable[[], Any]]] = None,
            extensions: Sequence[BaseServerExtension] | None = None,
    ) -> "AppServer":
        await super().initialize(
            service_name=service_name,
            router=router,
            config_dict=config_dict,
            scheduler_group=scheduler_group,
            middleware=middleware,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            extensions=extensions,
        )

        self._initialize_config_value_resolver()

        # controllersrv 等“宿主机控制服务”不参与服务注册/远程配置。
        # Host controller services (e.g. controllersrv) do not participate in registry/remote config.
        if not self._should_skip_registry():
            self.register_shutdown_callback(self._deregister_from_infrasrv)
        return self

    def _initialize_config_value_resolver(self) -> None:
        """初始化配置解析器并展开 ConfigValue 默认值 / Initialize resolver and materialize ConfigValue defaults."""
        snapshot = LinglongConfig.snapshot()
        self._config_value_resolver = ConfigValueResolver.from_snapshot(snapshot)
        defaults = self._config_value_resolver.materialize_defaults()
        if defaults:
            LinglongConfig.apply_updates(defaults)
            logger.info("ConfigValue wrappers initialized: %s", list(sorted(defaults.keys())))

    async def on_startup(self):  # noqa: D401 - lifecycle override
        await super().on_startup()
        if not self._should_skip_registry():
            self._registry_keepalive_task = asyncio.create_task(
                self._registry_keepalive_loop(),
                name=f"{self.service_name}-registry-keepalive",
            )

    async def on_shutdown(self) -> None:  # noqa: D401 - lifecycle override
        if self._registry_keepalive_task:
            self._registry_keepalive_task.cancel()
            try:
                await self._registry_keepalive_task
            except asyncio.CancelledError:
                pass
            self._registry_keepalive_task = None
        await super().on_shutdown()

    async def _before_resources_initialized(self) -> None:
        await self._fetch_service_config_from_remote(with_retry=True)

    def _add_internal_routes(self) -> None:
        if not self.app:
            return
        self.app.add_api_route("/internal/health", self._internal_health_check_handler, methods=["GET"])
        self.app.add_api_route("/internal/config/update", self._internal_config_update_handler, methods=["POST"])

    async def _internal_health_check_handler(self, request: Request):  # noqa: D401 - FastAPI handler
        return ORJSONResponse({
            "status": InstanceStatus.UP,
            "service": self.service_name,
            "instance_id": self.instance_id,
        })

    async def _internal_config_update_handler(self, request: Request):
        try:
            body = await request.json()
        except Exception as exc:  # pragma: no cover - FastAPI already validates JSON
            logger.error("Failed to parse config update payload: %s", exc, exc_info=True)
            return ORJSONResponse({"status": "error", "message": str(exc)}, status_code=400)

        config_payload = body.get("config") if isinstance(body, dict) else None
        if not config_payload:
            return ORJSONResponse({"status": "error", "message": "No config provided"}, status_code=400)

        self._update_config(config_payload)
        return ORJSONResponse({"status": "success", "message": "Config updated"})

    async def _fetch_service_config_from_remote(self, with_retry: bool = False) -> None:
        if self._should_skip_registry():
            logger.info("%s is a special service, skip remote config fetch", self.service_name)
            return

        url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/service_config"
        params = {"service_name": self.service_name}
        retries = 3 if with_retry else 0
        for attempt in range(retries + 1):
            try:
                resp = await http_client.get(url, params=params, timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT)
                resp.raise_for_status()
                data = await resp.json()
                remote_config = data.get("data", {}) if isinstance(data, dict) else {}
                if remote_config:
                    logger.info("Fetched remote config keys: %s", list(remote_config.keys()))
                    self._update_config(remote_config)
                return
            except Exception as exc:
                is_dev = LinglongConfig.DEBUG
                level = logger.warning if attempt < retries else logger.error
                level(
                    "Fetch remote config failed (attempt %s/%s): %s",
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                if attempt < retries:
                    await asyncio.sleep(3)
                elif is_dev:
                    logger.info("Development mode: remote config fetch failure can be ignored")

    def _update_config(self, remote_config: Dict[str, Any]) -> None:
        if not remote_config:
            return

        processed: Dict[str, Any] = {}
        for key, value in remote_config.items():
            config_key = key.upper()
            if not hasattr(LinglongConfig, config_key):
                logger.warning("Unknown remote config key '%s', skipping", config_key)
                continue

            local_value = getattr(LinglongConfig, config_key)
            try:
                new_value = self._config_value_resolver.resolve_update_value(
                    config_key=config_key,
                    current_value=local_value,
                    raw_value=value,
                )
                processed[config_key] = new_value
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to apply remote config for '%s': %s",
                    config_key,
                    exc,
                )

        if processed:
            LinglongConfig.apply_updates(processed)
            logger.info("Applied remote config: %s", list(processed.keys()))

    async def _register_to_infrasrv(self) -> None:
        register_host, container_hostname, network_alias, host_source = self._resolve_registration_host()
        instance_metadata = InstanceMetadata(
            container_hostname=container_hostname,
            network_alias=network_alias,
            register_host_source=host_source,
            app_host_binding=self.host,
        )
        service_metadata = ServiceMetadata(
            version="1.0.0",
            environment=(
                LinglongConst.ENVIRONMENT.DEVELOPMENT if LinglongConfig.DEBUG else LinglongConst.ENVIRONMENT.PRODUCTION),
        )
        payload = ServiceRegistryPayload(
            service_name=self.service_name or "",
            instance_id=self.instance_id or "",
            host=register_host,
            port=self.port or 0,
            internal_port=self.port or 0,
            health_check_url="/internal/health",
            container_name=container_hostname or network_alias,
            compose_service_name=network_alias,
            service_metadata=service_metadata,
            instance_metadata=instance_metadata,
        )
        payload_dict = payload.model_dump()
        payload_dict["instance_metadata"] = instance_metadata.model_dump(exclude_none=True)

        url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/registry/register"
        for attempt in range(4):
            try:
                resp = await http_client.post(
                    url,
                    json=payload_dict,
                    timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT,
                )
                if resp and resp.status == 200:
                    logger.info("Service registered: %s (%s)", self.service_name, self.instance_id)
                    return
                logger.warning("Register service failed, status=%s", resp.status if resp else "N/A")
            except Exception as exc:
                logger.warning("register attempt %s failed: %s", attempt + 1, exc)
            await asyncio.sleep(3)
        logger.error("All attempts to register %s failed", self.service_name)

    async def _register_keepalive_once(self) -> bool:
        """执行一次保活注册 / Execute one keepalive registration tick."""
        register_host, container_hostname, network_alias, host_source = self._resolve_registration_host()
        instance_metadata = InstanceMetadata(
            container_hostname=container_hostname,
            network_alias=network_alias,
            register_host_source=host_source,
            app_host_binding=self.host,
        )
        service_metadata = ServiceMetadata(
            version="1.0.0",
            environment=(
                LinglongConst.ENVIRONMENT.DEVELOPMENT if LinglongConfig.DEBUG else LinglongConst.ENVIRONMENT.PRODUCTION),
        )
        payload = ServiceRegistryPayload(
            service_name=self.service_name or "",
            instance_id=self.instance_id or "",
            host=register_host,
            port=self.port or 0,
            internal_port=self.port or 0,
            health_check_url="/internal/health",
            container_name=container_hostname or network_alias,
            compose_service_name=network_alias,
            service_metadata=service_metadata,
            instance_metadata=instance_metadata,
        )
        payload_dict = payload.model_dump()
        payload_dict["instance_metadata"] = instance_metadata.model_dump(exclude_none=True)

        url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/registry/register"
        try:
            resp = await http_client.post(
                url,
                json=payload_dict,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT,
            )
            if resp and resp.status == 200:
                return True
            logger.warning(
                "Registry keepalive failed, status=%s, service=%s, instance=%s",
                resp.status if resp else "N/A",
                self.service_name,
                self.instance_id,
            )
            return False
        except Exception as exc:
            logger.warning(
                "Registry keepalive request failed for %s (%s): %s",
                self.service_name,
                self.instance_id,
                exc,
            )
            return False

    async def _registry_keepalive_loop(self) -> None:
        """持续执行服务注册保活 / Keep registry heartbeat alive via periodic upsert."""
        interval_seconds = int(getattr(LinglongConfig, "SERVICE_REGISTRY_KEEPALIVE_SECONDS", 30) or 30)
        interval_seconds = max(interval_seconds, 5)

        # 启动即执行一次注册 / Register immediately on startup
        first_ok = await self._register_keepalive_once()
        if first_ok:
            logger.info("Service registered: %s (%s)", self.service_name, self.instance_id)
        else:
            logger.warning("Initial registry keepalive failed: %s (%s)", self.service_name, self.instance_id)

        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self._register_keepalive_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "Registry keepalive loop error for %s (%s): %s",
                    self.service_name,
                    self.instance_id,
                    exc,
                )

    async def _deregister_from_infrasrv(self) -> None:
        if self._should_skip_registry():
            return
        try:
            url = f"{LinglongConfig.INFRASRV_HOST}/v1/infrasrv/registry/deregister"
            params = {"service_name": self.service_name, "instance_id": self.instance_id}
            resp = await http_client.delete(url, params=params, timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT)
            if resp and resp.status == 200:
                logger.info("Service deregistered: %s (%s)", self.service_name, self.instance_id)
            else:
                logger.warning("Service deregister failed, status=%s", resp.status if resp else "N/A")
        except Exception as exc:
            logger.error("Deregister error: %s", exc)

    def _resolve_registration_host(self) -> Tuple[str, Optional[str], str, str]:
        container_hostname = (os.environ.get("HOSTNAME") or "").strip() or None
        network_alias = self._build_network_alias()
        host_source = "container_hostname"
        register_host = container_hostname or network_alias

        override_host = (os.environ.get("SERVICE_REGISTRY_HOST") or "").strip()
        if override_host:
            register_host = override_host
            host_source = "env:SERVICE_REGISTRY_HOST"
        elif (not container_hostname or
              self._looks_like_container_hostname(container_hostname) or
              container_hostname.lower() in WebServerConst.UNSAFE_HOSTS):
            register_host = network_alias
            host_source = "network_alias"
        return register_host, container_hostname, network_alias, host_source

    def _build_network_alias(self) -> str:
        explicit_alias = os.environ.get("SERVICE_NETWORK_ALIAS")
        if explicit_alias and explicit_alias.strip():
            return explicit_alias.strip()
        suffix = os.environ.get("SERVICE_NETWORK_SUFFIX", ".service")
        base_name = self.service_name or ""
        if base_name.endswith(suffix):
            return base_name
        return f"{base_name}{suffix}" if base_name else suffix.lstrip('.')

    @staticmethod
    def _looks_like_container_hostname(hostname: Optional[str]) -> bool:
        if not hostname:
            return False
        candidate = hostname.strip().lower()
        return bool(WebServerConst.CONTAINER_ID_PATTERN.fullmatch(candidate))

    def _should_skip_registry(self) -> bool:
        # controllersrv 是宿主机控制服务：不注册、不拉取远端配置、不发心跳。
        # controllersrv is a host controller service: skip registry/remote config/heartbeat.
        if bool(getattr(LinglongConfig, "IS_CONTROLLER_SERVICE", False)):
            logger.info("%s is a controller service, skip service registry", self.service_name)
            return True

        # 可通过配置显式禁用服务注册（例如某些 BFF/工具型服务）。
        # Allow explicit opt-out via config for services that should not register.
        if bool(getattr(LinglongConfig, "SKIP_SERVICE_REGISTRY", False)):
            logger.info("%s is configured to skip service registry", self.service_name)
            return True
        return False

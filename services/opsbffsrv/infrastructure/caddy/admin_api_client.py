"""Caddy Admin API client.

提供与 Caddy Admin API 交互的功能。
Provides helpers to interact with Caddy Admin API.

Important:
- In some dev flows, `caddy.internal` may not exist (caddy not started yet).
  Connection/DNS failures are treated as non-fatal warnings.
"""

import asyncio
import copy
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from aiohttp import (
    ClientConnectorDNSError,
    ClientConnectorError,
    ClientOSError,
    ClientResponseError,
)

from linglong_web import (
    HTTPClientConfig,
    http_client,
)
from linglong_web.utils import logger

from cancan_microstack.public.const.caddy_consts import InternalRequestPath
from cancan_microstack.public.error import HTTPException


class CaddyAdminClient:
    """Caddy Admin API 客户端"""

    _MANAGED_ROUTE_GROUP = "cancan_managed_routes"
    _MANAGED_RATE_LIMIT_GROUP = "cancan_managed_rate_limits"

    def __init__(self, admin_url: str = "http://caddy.internal:2019"):
        """
        初始化 Caddy Admin API 客户端
        
        Args:
            admin_url: Caddy Admin API 地址
        """
        self.admin_url = admin_url.rstrip('/')
        self._last_load_error: Optional[str] = None

    async def get_config(self) -> Optional[Dict[str, Any]]:
        """
        获取当前 Caddy 配置
        
        Returns:
            配置字典或 None
        """
        try:
            url = f"{self.admin_url}/config/"
            resp = await http_client.get(
                url,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )
            if resp and resp.status == 200:
                return await resp.json()
            logger.warning(f"Failed to get Caddy config: {resp.status if resp else 'No response'}")
            return None
        except HTTPException as e:
            logger.warning(f"HTTP error getting Caddy config: {e}")
            return None
        except (ClientConnectorDNSError, ClientConnectorError, ClientOSError, ClientResponseError, asyncio.TimeoutError) as e:
            logger.warning("Caddy Admin API unreachable (%s): %s", self.admin_url, e)
            return None
        except Exception as e:
            logger.error("Error getting Caddy config: %s", e, exc_info=True)
            return None

    async def load_config(self, config: Dict[str, Any]) -> bool:
        """
        加载完整的 Caddy 配置
        
        Args:
            config: 完整配置字典
            
        Returns:
            是否成功
        """
        try:
            url = f"{self.admin_url}/load"
            resp = await http_client.post(
                url,
                json=config,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )
            if resp and resp.status == 200:
                self._last_load_error = None
                logger.info("Caddy config loaded successfully")
                return True
            response_status = resp.status if resp else 'No response'
            response_text = None
            if resp:
                try:
                    response_text = await resp.text()
                except Exception as e:
                    logger.warning("Failed to read Caddy load error body: %s", e)
            self._last_load_error = response_text or str(response_status)
            logger.warning(
                "Failed to load Caddy config: %s, body=%s",
                response_status,
                response_text,
            )
            return False
        except HTTPException as e:
            self._last_load_error = str(e)
            logger.warning(f"HTTP error loading Caddy config: {e}")
            return False
        except (ClientConnectorDNSError, ClientConnectorError, ClientOSError, ClientResponseError, asyncio.TimeoutError) as e:
            self._last_load_error = str(e)
            logger.warning("Caddy Admin API unreachable (%s): %s", self.admin_url, e)
            return False
        except Exception as e:
            self._last_load_error = str(e)
            logger.error("Error loading Caddy config: %s", e, exc_info=True)
            return False

    async def update_route(self, route_id: str, route_config: Dict[str, Any]) -> bool:
        """
        更新单个路由配置
        
        Args:
            route_id: 路由标识符
            route_config: 路由配置
            
        Returns:
            是否成功
        """
        try:
            url = f"{self.admin_url}/config/apps/http/servers/srv0/routes/{route_id}"
            resp = await http_client.patch(
                url,
                json=route_config,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )
            if resp and resp.status == 200:
                logger.info(f"Route {route_id} updated successfully")
                return True
            logger.warning(f"Failed to update route {route_id}: {resp.status if resp else 'No response'}")
            return False
        except HTTPException as e:
            logger.warning(f"HTTP error updating route {route_id}: {e}")
            return False
        except (ClientConnectorDNSError, ClientConnectorError, ClientOSError, ClientResponseError, asyncio.TimeoutError) as e:
            logger.warning("Caddy Admin API unreachable (%s): %s", self.admin_url, e)
            return False
        except Exception as e:
            logger.error("Error updating route %s: %s", route_id, e, exc_info=True)
            return False

    async def add_route(self, route_config: Dict[str, Any]) -> bool:
        """
        添加新路由
        
        Args:
            route_config: 路由配置
            
        Returns:
            是否成功
        """
        try:
            url = f"{self.admin_url}/config/apps/http/servers/srv0/routes"
            resp = await http_client.post(
                url,
                json=route_config,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )
            if resp and resp.status == 200:
                logger.info("Route added successfully")
                return True
            logger.warning(f"Failed to add route: {resp.status if resp else 'No response'}")
            return False
        except HTTPException as e:
            logger.warning(f"HTTP error adding route: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding route: {e}", exc_info=True)
            return False

    async def delete_route(self, route_id: str) -> bool:
        """
        删除路由
        
        Args:
            route_id: 路由标识符
            
        Returns:
            是否成功
        """
        try:
            url = f"{self.admin_url}/config/apps/http/servers/srv0/routes/{route_id}"
            resp = await http_client.delete(
                url,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )
            if resp and resp.status == 200:
                logger.info(f"Route {route_id} deleted successfully")
                return True
            logger.warning(f"Failed to delete route {route_id}: {resp.status if resp else 'No response'}")
            return False
        except HTTPException as e:
            logger.warning(f"HTTP error deleting route {route_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error deleting route {route_id}: {e}", exc_info=True)
            return False

    async def reload_config(self) -> bool:
        """
        重新加载配置（优雅重启）
        
        Returns:
            是否成功
        """
        try:
            # Caddy Admin API 会自动应用配置，无需显式重载
            # 但我们可以验证配置是否有效
            config = await self.get_config()
            return config is not None
        except Exception as e:
            logger.error(f"Error reloading Caddy config: {e}", exc_info=True)
            return False

    async def get_metrics(self) -> Optional[str]:
        """
        获取 Prometheus 格式的监控指标
        
        Returns:
            指标文本或 None
        """
        try:
            # Caddy metrics endpoint (需要在 Caddyfile 中配置)
            url = f"{self.admin_url.replace(':2019', ':2020')}/metrics"
            resp = await http_client.get(
                url,
                timeout=HTTPClientConfig.INTERNAL_SERVICE_TIMEOUT
            )
            if resp and resp.status == 200:
                return await resp.text()
            logger.warning(f"Failed to get Caddy metrics: {resp.status if resp else 'No response'}")
            return None
        except HTTPException as e:
            logger.warning(f"HTTP error getting Caddy metrics: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting Caddy metrics: {e}", exc_info=True)
            return None

    async def build_route_config(
            self,
            domain: str,
            path_pattern: str,
            upstream_host: str,
            upstream_port: int,
            enable_https: bool = True,
            force_https: bool = True,
            enable_waf: bool = True,
            waf_rule_set: str = "default",
            strip_path_prefix: Optional[str] = None,
            add_path_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        构建路由配置对象
        
        Args:
            domain: 域名
            path_pattern: 路径模式
            upstream_host: 上游主机
            upstream_port: 上游端口
            enable_https: 启用 HTTPS
            force_https: 强制 HTTPS
            enable_waf: 启用 WAF
            waf_rule_set: WAF 规则集
            strip_path_prefix: 去除路径前缀
            add_path_prefix: 添加路径前缀
            
        Returns:
            路由配置字典
        """
        # 构建匹配器
        matchers = []
        if domain and domain != "*":
            matchers.append({"host": [domain]})
        if path_pattern != "/*":
            matchers.append({"path": [path_pattern]})

        # 构建处理器
        handlers = []

        # WAF 处理器（如果启用）
        if enable_waf:
            directives = [
                "Include /etc/caddy/waf/coraza.conf",
            ]

            # 当前 **仅支持 default WAF 规则集**：所有路由统一加载 /etc/caddy/waf/coraza.conf。
            # 尚未实现"按路由切换 WAF 规则集"（即不会根据 waf_rule_set 映射到不同规则文件）。
            # 因此传入任何非 default 的 waf_rule_set 都会被忽略并回退到 default，
            # 这里显式告警以免给调用方造成"已按规则集生效"的错觉。
            # Only the "default" WAF rule set is supported for now; non-default values fall back to default.
            if waf_rule_set and waf_rule_set != "default":
                logger.warning(
                    "WAF rule set %r is not supported (only 'default' is implemented); "
                    "falling back to the default rule set",
                    waf_rule_set,
                )

            handlers.append({
                "handler": "coraza_waf",
                "directives": directives
            })

        # 路径重写处理器
        if strip_path_prefix or add_path_prefix:
            rewrite = {}
            if strip_path_prefix:
                rewrite["strip_path_prefix"] = strip_path_prefix
            if add_path_prefix:
                rewrite["uri"] = f"{add_path_prefix}{{http.request.uri}}"
            handlers.append({
                "handler": "rewrite",
                **rewrite
            })

        # 反向代理处理器
        handlers.append({
            "handler": "reverse_proxy",
            "upstreams": [{
                "dial": f"{upstream_host}:{upstream_port}"
            }],
            "health_checks": {
                "active": {
                    "path": InternalRequestPath.HEALTH_CHECK.value,
                    "interval": "30s",
                    "timeout": "5s"
                }
            }
        })

        route_config = {
            "group": self._MANAGED_ROUTE_GROUP,
            "match": matchers,
            "handle": handlers
        }

        # HTTPS 重定向（如果强制 HTTPS）
        if enable_https and force_https:
            route_config["terminal"] = True

        return route_config

    async def apply_routes_batch(self, routes: List[Dict[str, Any]]) -> bool:
        """
        批量应用路由配置
        
        Args:
            routes: 路由配置列表
            
        Returns:
            是否成功
        """
        try:
            # 获取当前配置
            config = await self.get_config()
            if not config:
                logger.error("Failed to get current Caddy config")
                return False

            # 更新路由配置
            if "apps" not in config:
                config["apps"] = {}
            if "http" not in config["apps"]:
                config["apps"]["http"] = {"servers": {}}
            if "servers" not in config["apps"]["http"]:
                config["apps"]["http"]["servers"] = {}

            servers = config["apps"]["http"]["servers"]
            target_server_key = self._resolve_target_server_key(servers)
            if target_server_key not in servers:
                servers[target_server_key] = {"routes": []}

            server = servers[target_server_key]
            existing_routes = server.get("routes", [])

            # 保留非托管路由，替换托管路由
            # Keep non-managed routes and replace managed routes only
            preserved_routes = [
                route for route in existing_routes
                if route.get("group") != self._MANAGED_ROUTE_GROUP
            ]

            fallback_routes = []
            normal_routes = []
            for route in preserved_routes:
                if self._is_not_found_fallback_route(route):
                    fallback_routes.append(route)
                else:
                    normal_routes.append(route)

            server["routes"] = normal_routes + routes + fallback_routes
            logger.info(
                "Applying %s managed routes to Caddy server %s",
                len(routes),
                target_server_key,
            )

            # 加载新配置
            load_ok = await self.load_config(config)
            if load_ok:
                return True

            # 模块缺失时自动移除 WAF 处理器并重试
            # Auto-disable WAF handlers when module is missing and retry
            if self._is_waf_module_missing(self._last_load_error):
                logger.warning("Caddy WAF module missing, retrying without WAF handlers")
                server["routes"] = normal_routes + self._strip_waf_handlers(routes) + fallback_routes
                return await self.load_config(config)

            return False
        except HTTPException as e:
            logger.warning(f"HTTP error applying routes batch: {e}")
            return False
        except Exception as e:
            logger.error(f"Error applying routes batch: {e}", exc_info=True)
            return False

    async def build_rate_limit_config(self, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """构建限流规则对应的 Caddy 路由配置
        Build Caddy route configs for a rate-limit rule
        """
        rule_name = str(rule.get("rule_name") or f"rule_{rule.get('id', 'unknown')}")
        limit_value = int(rule.get("limit_value") or 0)
        limit_window = int(rule.get("limit_window") or 60)
        limit_key = str(rule.get("limit_key") or "ip")
        block_status_code = int(rule.get("block_status_code") or 429)
        block_message = str(rule.get("block_message") or "Too Many Requests")

        if limit_value <= 0:
            return []

        matcher = self._build_rate_limit_matcher(rule)

        route_list: List[Dict[str, Any]] = []

        blacklist_ips = [ip for ip in (rule.get("blacklist_ips") or []) if ip]
        if blacklist_ips:
            blacklist_match = copy.deepcopy(matcher) if matcher else {}
            blacklist_match["remote_ip"] = {"ranges": blacklist_ips}
            route_list.append({
                "group": self._MANAGED_RATE_LIMIT_GROUP,
                "match": [blacklist_match] if blacklist_match else [],
                "handle": [
                    {
                        "handler": "static_response",
                        "status_code": block_status_code,
                        "body": block_message,
                    }
                ],
                "terminal": True,
            })

        key_template = self._build_rate_limit_key_template(limit_key, rule)
        zone_config: Dict[str, Any] = {
            "key": key_template,
            "window": f"{limit_window}s",
            "max_events": limit_value,
        }
        if matcher:
            zone_config["match"] = [matcher]

        rate_limit_route = {
            "group": self._MANAGED_RATE_LIMIT_GROUP,
            "handle": [
                {
                    "handler": "rate_limit",
                    "rate_limits": {
                        rule_name: zone_config,
                    },
                }
            ],
        }
        route_list.append(rate_limit_route)
        return route_list

    async def apply_rate_limits_batch(self, rate_limit_routes: List[Dict[str, Any]]) -> bool:
        """批量应用限流规则到 Caddy
        Apply managed rate-limit routes to Caddy in batch
        """
        try:
            config = await self.get_config()
            if not config:
                logger.error("Failed to get current Caddy config")
                return False

            if "apps" not in config:
                config["apps"] = {}
            if "http" not in config["apps"]:
                config["apps"]["http"] = {"servers": {}}
            if "servers" not in config["apps"]["http"]:
                config["apps"]["http"]["servers"] = {}

            servers = config["apps"]["http"]["servers"]
            target_server_key = self._resolve_target_server_key(servers)
            if target_server_key not in servers:
                servers[target_server_key] = {"routes": []}

            server = servers[target_server_key]
            existing_routes = server.get("routes", [])

            preserved_routes = [
                route for route in existing_routes
                if route.get("group") != self._MANAGED_RATE_LIMIT_GROUP
            ]

            fallback_routes: List[Dict[str, Any]] = []
            managed_proxy_routes: List[Dict[str, Any]] = []
            normal_routes: List[Dict[str, Any]] = []
            for route in preserved_routes:
                if self._is_not_found_fallback_route(route):
                    fallback_routes.append(route)
                elif route.get("group") == self._MANAGED_ROUTE_GROUP:
                    managed_proxy_routes.append(route)
                else:
                    normal_routes.append(route)

            server["routes"] = rate_limit_routes + normal_routes + managed_proxy_routes + fallback_routes
            logger.info(
                "Applying %s managed rate-limit routes to Caddy server %s",
                len(rate_limit_routes),
                target_server_key,
            )

            load_ok = await self.load_config(config)
            if load_ok:
                return True

            if self._is_rate_limit_module_missing(self._last_load_error):
                logger.warning("Caddy rate_limit module missing, cannot apply rate limits")
            return False
        except Exception as e:
            logger.error("Error applying rate limits batch: %s", e, exc_info=True)
            return False

    def _build_rate_limit_matcher(self, rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        matcher: Dict[str, Any] = {}
        match_type = str(rule.get("match_type") or "all")
        match_pattern = rule.get("match_pattern")
        match_domain = rule.get("match_domain")

        if match_domain:
            matcher["host"] = [str(match_domain)]

        if match_type == "path" and match_pattern:
            matcher["path"] = [str(match_pattern)]
        elif match_type == "domain" and match_pattern and "host" not in matcher:
            matcher["host"] = [str(match_pattern)]
        elif match_type == "ip" and match_pattern:
            matcher["remote_ip"] = {"ranges": [str(match_pattern)]}
        elif match_type == "header" and match_pattern:
            header_name, header_value = self._parse_header_pattern(str(match_pattern))
            if header_name:
                matcher["header"] = {header_name: [header_value]} if header_value else {header_name: []}

        whitelist_ips = [ip for ip in (rule.get("whitelist_ips") or []) if ip]
        if whitelist_ips:
            matcher.setdefault("not", []).append({"remote_ip": {"ranges": whitelist_ips}})

        return matcher or None

    def _build_rate_limit_key_template(self, limit_key: str, rule: Dict[str, Any]) -> str:
        metadata = rule.get("rule_metadata") or {}
        if limit_key == "ip":
            return "{http.request.remote.host}"
        if limit_key == "header":
            header_name = metadata.get("key_header") or metadata.get("header_name")
            if header_name:
                return f"{{http.request.header.{header_name}}}"
            return "{http.request.remote.host}"
        if limit_key == "cookie":
            cookie_name = metadata.get("cookie_name") or "session"
            return f"{{http.request.cookie.{cookie_name}}}"
        if limit_key == "path":
            return "{http.request.uri.path}"
        return "{http.request.remote.host}"

    def _parse_header_pattern(self, pattern: str) -> Tuple[Optional[str], Optional[str]]:
        if ":" not in pattern:
            return pattern.strip(), None
        key, value = pattern.split(":", 1)
        return key.strip(), value.strip()

    def _is_rate_limit_module_missing(self, error_text: Optional[str]) -> bool:
        if not error_text:
            return False
        return "unknown module: http.handlers.rate_limit" in error_text

    def _strip_waf_handlers(self, routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        移除 WAF 处理器，避免加载不存在的模块
        Remove WAF handlers to avoid loading missing modules
        """
        sanitized = copy.deepcopy(routes)
        for route in sanitized:
            handlers = route.get("handle", [])
            route["handle"] = [
                handler for handler in handlers
                if handler.get("handler") not in {"coraza_waf", "coraza"}
            ]
        return sanitized

    def _is_waf_module_missing(self, error_text: Optional[str]) -> bool:
        if not error_text:
            return False
        return (
            "unknown module: http.handlers.coraza_waf" in error_text
            or "unknown module: http.handlers.coraza" in error_text
        )

    def _resolve_target_server_key(self, servers: Dict[str, Any]) -> str:
        """
        选择应写入路由的 Caddy HTTP server
        Select the Caddy HTTP server key for managed routes
        """
        if not servers:
            return "srv0"

        preferred_ports = [":8080", ":80", ":443"]
        for preferred_port in preferred_ports:
            for server_key, server_config in servers.items():
                listen = server_config.get("listen", [])
                if any(preferred_port in str(item) for item in listen):
                    return server_key

        return next(iter(servers.keys()))

    def _is_not_found_fallback_route(self, route: Dict[str, Any]) -> bool:
        """
        判断是否为 Caddy 默认 404 回退路由
        Determine whether route is a catch-all 404 fallback route
        """
        if route.get("match"):
            return False

        handlers = route.get("handle", [])
        for handler in handlers:
            if (
                handler.get("handler") == "subroute"
                and isinstance(handler.get("routes"), list)
            ):
                for subroute in handler.get("routes", []):
                    for subhandler in subroute.get("handle", []):
                        if (
                            subhandler.get("handler") == "static_response"
                            and subhandler.get("status_code") == 404
                        ):
                            return True
            if (
                handler.get("handler") == "static_response"
                and handler.get("status_code") == 404
            ):
                return True

        return False


# 全局实例
caddy_admin_client = CaddyAdminClient()

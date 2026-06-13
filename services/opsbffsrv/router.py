"""
opsbffsrv 路由配置
提供运营管理相关的API接口
"""
import http

from linglong_web import BaseRoute
from cancan_microstack.services.opsbffsrv.interface.api.service_config import (
    get_service_config_handler,
    insert_service_config_handler,
    update_service_config_handler,
    get_all_service_configs_handler,
    delete_service_config_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.service_registry import (
    get_service_instances_handler,
    get_all_instances_handler,
    get_instance_handler,
    get_all_service_names_handler,
    get_services_overview_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.async_operation_api import (
    async_start_service_handler,
    async_stop_service_handler,
    async_restart_service_handler,
    get_operation_status_handler,
    list_operations_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.instance_management_api import (
    list_service_instances_handler,
    get_instance_detail_handler,
    get_service_instance_stats_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.service_logs_api import (
    get_service_logs_handler,
    get_service_logs_by_service_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.log_query_api import (
    search_business_logs_handler,
)
# Caddy 管理接口
from cancan_microstack.services.opsbffsrv.interface.api.caddy.route_api import (
    create_route_handler,
    update_route_handler,
    get_route_handler,
    list_routes_handler,
    delete_route_handler,
    toggle_route_handler,
    sync_all_routes_handler,
    get_route_statistics_handler,
    get_routes_by_domain_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.caddy.rate_limit_api import (
    create_rate_limit_handler,
    update_rate_limit_handler,
    get_rate_limit_handler,
    list_rate_limits_handler,
    delete_rate_limit_handler,
    toggle_rate_limit_handler,
    add_whitelist_ips_handler,
    remove_whitelist_ips_handler,
    add_blacklist_ips_handler,
    remove_blacklist_ips_handler,
    get_rate_limit_statistics_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.caddy.certificate_api import (
    register_certificate_handler,
    update_certificate_handler,
    get_certificate_handler,
    list_certificates_handler,
    delete_certificate_handler,
    renew_certificate_handler,
    toggle_auto_renew_handler,
    list_expiring_certificates_handler,
    get_certificate_statistics_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.caddy.stats_api import (
    get_realtime_global_stats_handler,
    get_realtime_service_stats_handler,
    get_global_trend_handler,
    get_service_trend_handler,
    get_route_trend_handler,
    get_top_countries_handler,
    get_top_ips_handler,
    cleanup_old_stats_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.caddy.access_log_api import (
    search_logs_handler,
    get_security_events_handler,
    analyze_geographic_distribution_handler,
    analyze_status_code_distribution_handler,
    detect_suspicious_ips_handler,
    analyze_error_patterns_handler,
    cleanup_old_logs_handler,
)
# 数据库 schema 管理接口
from cancan_microstack.services.opsbffsrv.interface.api.db_admin_api import (
    schema_apply_handler,
    schema_diff_handler,
    schema_rebuild_database_handler,
    schema_rebuild_tables_handler,
)
# 数据库初始化接口
from cancan_microstack.services.opsbffsrv.interface.api.db_init_api import (
    initialize_databases_handler,
    incremental_build_handler,
    get_database_status_handler,
)
# pgweb 代理接口
from cancan_microstack.services.opsbffsrv.interface.api.pgweb_proxy_api import (
    pgweb_proxy_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.redis_commander_proxy_api import (
    redis_commander_proxy_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.mongo_express_proxy_api import (
    mongo_express_proxy_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.rabbitmq_mgmt_proxy_api import (
    rabbitmq_mgmt_proxy_handler,
    rabbitmq_mgmt_login_bypass_probe_handler,
)
from cancan_microstack.services.opsbffsrv.interface.api.workflow_ops_api import (
    list_workflows_handler,
    get_workflow_handler,
    list_runs_handler,
    get_run_graph_status_handler,
    create_workflow_handler,
    get_workflow_stats_handler,
    trigger_workflow_handler,
    get_node_history_handler,
    update_workflow_handler,
    delete_workflow_handler,
    toggle_workflow_handler,
    duplicate_workflow_handler,
    publish_workflow_handler,
    validate_workflow_handler,
    list_workflow_versions_handler,
    rollback_workflow_handler,
    list_workflow_alerts_handler,
    acknowledge_workflow_alert_handler,
    resolve_workflow_alert_handler,
)
# 认证管理接口
from cancan_microstack.services.opsbffsrv.interface.api.auth_api import (
    get_captcha_handler,
    login_handler,
    totp_setup_handler,
    totp_bind_handler,
    totp_verify_handler,
    check_session_handler,
    logout_handler,
)

router_list = [
    # === 服务配置管理 ===
    # 获取单个服务配置
    BaseRoute(
        path="/v1/opsbffsrv/service_config",
        method=http.HTTPMethod.GET,
        handler=get_service_config_handler,
    ),
    # 获取所有服务配置
    BaseRoute(
        path="/v1/opsbffsrv/service_config/all",
        method=http.HTTPMethod.GET,
        handler=get_all_service_configs_handler,
    ),
    # 新增服务配置
    BaseRoute(
        path="/v1/opsbffsrv/service_config",
        method=http.HTTPMethod.POST,
        handler=insert_service_config_handler,
    ),
    # 更新服务配置
    BaseRoute(
        path="/v1/opsbffsrv/service_config",
        method=http.HTTPMethod.PUT,
        handler=update_service_config_handler,
    ),
    # 删除服务配置
    BaseRoute(
        path="/v1/opsbffsrv/service_config",
        method=http.HTTPMethod.DELETE,
        handler=delete_service_config_handler,
    ),

    # === 服务注册与发现 ===
    # 获取指定服务的所有实例
    BaseRoute(
        path="/v1/opsbffsrv/registry/instances",
        method=http.HTTPMethod.GET,
        handler=get_service_instances_handler,
    ),
    # 获取所有服务的全部实例
    BaseRoute(
        path="/v1/opsbffsrv/registry/instances/all",
        method=http.HTTPMethod.GET,
        handler=get_all_instances_handler,
    ),
    # 获取单个实例详情
    BaseRoute(
        path="/v1/opsbffsrv/registry/instance",
        method=http.HTTPMethod.GET,
        handler=get_instance_handler,
    ),
    # 获取所有已注册的服务名称
    BaseRoute(
        path="/v1/opsbffsrv/registry/services",
        method=http.HTTPMethod.GET,
        handler=get_all_service_names_handler,
    ),
    # 获取服务概览信息
    BaseRoute(
        path="/v1/opsbffsrv/registry/services/overview",
        method=http.HTTPMethod.GET,
        handler=get_services_overview_handler,
    ),
    # 异步启动服务
    BaseRoute(
        path="/v1/opsbffsrv/async/service/start",
        method=http.HTTPMethod.POST,
        handler=async_start_service_handler,
    ),
    # 异步停止服务
    BaseRoute(
        path="/v1/opsbffsrv/async/service/stop",
        method=http.HTTPMethod.POST,
        handler=async_stop_service_handler,
    ),
    # 异步重启服务
    BaseRoute(
        path="/v1/opsbffsrv/async/service/restart",
        method=http.HTTPMethod.POST,
        handler=async_restart_service_handler,
    ),
    # 获取异步操作状态
    BaseRoute(
        path="/v1/opsbffsrv/operation/status",
        method=http.HTTPMethod.GET,
        handler=get_operation_status_handler,
    ),
    # 列出异步操作历史
    BaseRoute(
        path="/v1/opsbffsrv/operation/list",
        method=http.HTTPMethod.GET,
        handler=list_operations_handler,
    ),

    # === 实例管理 ===
    # 列出服务实例
    BaseRoute(
        path="/v1/opsbffsrv/instance/list",
        method=http.HTTPMethod.GET,
        handler=list_service_instances_handler,
    ),
    # 获取实例详情
    BaseRoute(
        path="/v1/opsbffsrv/instance/detail",
        method=http.HTTPMethod.GET,
        handler=get_instance_detail_handler,
    ),
    # 获取服务实例统计信息
    BaseRoute(
        path="/v1/opsbffsrv/instance/stats",
        method=http.HTTPMethod.GET,
        handler=get_service_instance_stats_handler,
    ),

    # === 服务日志 ===
    # 获取服务日志
    BaseRoute(
        path="/v1/opsbffsrv/service_logs",
        method=http.HTTPMethod.GET,
        handler=get_service_logs_handler,
    ),
    # 按服务获取日志
    BaseRoute(
        path="/v1/opsbffsrv/service_logs/by_service",
        method=http.HTTPMethod.GET,
        handler=get_service_logs_by_service_handler,
    ),

    # === 业务日志查询 ===
    BaseRoute(
        path="/v1/opsbffsrv/logs/search",
        method=http.HTTPMethod.POST,
        handler=search_business_logs_handler,
    ),

    # === Caddy 路由管理 ===
    # 创建路由
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes",
        method=http.HTTPMethod.POST,
        handler=create_route_handler,
    ),
    # 获取路由列表
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes",
        method=http.HTTPMethod.GET,
        handler=list_routes_handler,
    ),
    # 同步所有路由配置
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/sync",
        method=http.HTTPMethod.POST,
        handler=sync_all_routes_handler,
    ),
    # 获取路由统计信息
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/statistics",
        method=http.HTTPMethod.GET,
        handler=get_route_statistics_handler,
    ),
    # 根据域名获取路由
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/by-domain/{domain}",
        method=http.HTTPMethod.GET,
        handler=get_routes_by_domain_handler,
    ),
    # 获取单个路由
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/{route_id}",
        method=http.HTTPMethod.GET,
        handler=get_route_handler,
    ),
    # 更新路由
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/{route_id}",
        method=http.HTTPMethod.PUT,
        handler=update_route_handler,
    ),
    # 删除路由
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/{route_id}",
        method=http.HTTPMethod.DELETE,
        handler=delete_route_handler,
    ),
    # 切换路由启用/禁用状态
    BaseRoute(
        path="/v1/opsbffsrv/caddy/routes/{route_id}/toggle",
        method=http.HTTPMethod.POST,
        handler=toggle_route_handler,
    ),

    # === Caddy 速率限制管理 ===
    # 创建速率限制规则
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits",
        method=http.HTTPMethod.POST,
        handler=create_rate_limit_handler,
    ),
    # 获取速率限制规则列表
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits",
        method=http.HTTPMethod.GET,
        handler=list_rate_limits_handler,
    ),
    # 获取速率限制统计信息
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/statistics",
        method=http.HTTPMethod.GET,
        handler=get_rate_limit_statistics_handler,
    ),
    # 获取单个速率限制规则
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}",
        method=http.HTTPMethod.GET,
        handler=get_rate_limit_handler,
    ),
    # 更新速率限制规则
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}",
        method=http.HTTPMethod.PUT,
        handler=update_rate_limit_handler,
    ),
    # 删除速率限制规则
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}",
        method=http.HTTPMethod.DELETE,
        handler=delete_rate_limit_handler,
    ),
    # 切换速率限制规则启用/禁用状态
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}/toggle",
        method=http.HTTPMethod.POST,
        handler=toggle_rate_limit_handler,
    ),
    # 添加白名单IP
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}/whitelist",
        method=http.HTTPMethod.POST,
        handler=add_whitelist_ips_handler,
    ),
    # 移除白名单IP
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}/whitelist",
        method=http.HTTPMethod.DELETE,
        handler=remove_whitelist_ips_handler,
    ),
    # 添加黑名单IP
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}/blacklist",
        method=http.HTTPMethod.POST,
        handler=add_blacklist_ips_handler,
    ),
    # 移除黑名单IP
    BaseRoute(
        path="/v1/opsbffsrv/caddy/rate-limits/{rule_id}/blacklist",
        method=http.HTTPMethod.DELETE,
        handler=remove_blacklist_ips_handler,
    ),

    # === Caddy 证书管理 ===
    # 获取即将过期的证书列表
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/expiring",
        method=http.HTTPMethod.GET,
        handler=list_expiring_certificates_handler,
    ),
    # 获取证书统计信息
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/statistics",
        method=http.HTTPMethod.GET,
        handler=get_certificate_statistics_handler,
    ),
    # 注册新证书
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates",
        method=http.HTTPMethod.POST,
        handler=register_certificate_handler,
    ),
    # 获取证书列表
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates",
        method=http.HTTPMethod.GET,
        handler=list_certificates_handler,
    ),
    # 更新证书信息
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/{cert_id}",
        method=http.HTTPMethod.PUT,
        handler=update_certificate_handler,
    ),
    # 获取单个证书
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/{cert_id}",
        method=http.HTTPMethod.GET,
        handler=get_certificate_handler,
    ),
    # 删除证书
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/{cert_id}",
        method=http.HTTPMethod.DELETE,
        handler=delete_certificate_handler,
    ),
    # 续订证书
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/{cert_id}/renew",
        method=http.HTTPMethod.POST,
        handler=renew_certificate_handler,
    ),
    # 切换自动续订状态
    BaseRoute(
        path="/v1/opsbffsrv/caddy/certificates/{cert_id}/auto-renew",
        method=http.HTTPMethod.POST,
        handler=toggle_auto_renew_handler,
    ),

    # === Caddy 统计信息 ===
    # 获取全局实时统计
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/realtime/global",
        method=http.HTTPMethod.GET,
        handler=get_realtime_global_stats_handler,
    ),
    # 获取单个服务的实时统计
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/realtime/service/{service_name}",
        method=http.HTTPMethod.GET,
        handler=get_realtime_service_stats_handler,
    ),
    # 获取全局流量趋势
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/trend/global",
        method=http.HTTPMethod.GET,
        handler=get_global_trend_handler,
    ),
    # 获取单个服务的流量趋势
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/trend/service/{service_name}",
        method=http.HTTPMethod.GET,
        handler=get_service_trend_handler,
    ),
    # 获取单个路由的流量趋势
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/trend/route/{route_id}",
        method=http.HTTPMethod.GET,
        handler=get_route_trend_handler,
    ),
    # 获取访问量最高的国家排名
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/top/countries",
        method=http.HTTPMethod.GET,
        handler=get_top_countries_handler,
    ),
    # 获取访问量最高的IP排名
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/top/ips",
        method=http.HTTPMethod.GET,
        handler=get_top_ips_handler,
    ),
    # 清理旧的统计数据
    BaseRoute(
        path="/v1/opsbffsrv/caddy/stats/cleanup",
        method=http.HTTPMethod.POST,
        handler=cleanup_old_stats_handler,
    ),

    # === Caddy 访问日志 ===
    # 搜索访问日志
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/search",
        method=http.HTTPMethod.POST,
        handler=search_logs_handler,
    ),
    # 获取安全事件日志
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/security-events",
        method=http.HTTPMethod.GET,
        handler=get_security_events_handler,
    ),
    # 分析地理位置分布
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/analysis/geographic",
        method=http.HTTPMethod.GET,
        handler=analyze_geographic_distribution_handler,
    ),
    # 分析状态码分布
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/analysis/status-codes",
        method=http.HTTPMethod.GET,
        handler=analyze_status_code_distribution_handler,
    ),
    # 检测可疑IP
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/analysis/suspicious-ips",
        method=http.HTTPMethod.GET,
        handler=detect_suspicious_ips_handler,
    ),
    # 分析错误模式
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/analysis/error-patterns",
        method=http.HTTPMethod.GET,
        handler=analyze_error_patterns_handler,
    ),
    # 清理旧的访问日志
    BaseRoute(
        path="/v1/opsbffsrv/caddy/logs/cleanup",
        method=http.HTTPMethod.POST,
        handler=cleanup_old_logs_handler,
    ),

    # === 数据库 Schema 管理 ===
    # 应用 Schema 变更
    BaseRoute(
        path="/v1/opsbffsrv/db/schema/apply",
        method=http.HTTPMethod.POST,
        handler=schema_apply_handler,
    ),
    # 比对 Schema 差异
    BaseRoute(
        path="/v1/opsbffsrv/db/schema/diff",
        method=http.HTTPMethod.POST,
        handler=schema_diff_handler,
    ),
    # 重建整个数据库
    BaseRoute(
        path="/v1/opsbffsrv/db/schema/rebuild",
        method=http.HTTPMethod.POST,
        handler=schema_rebuild_database_handler,
    ),
    # 重建指定的表
    BaseRoute(
        path="/v1/opsbffsrv/db/schema/rebuild_tables",
        method=http.HTTPMethod.POST,
        handler=schema_rebuild_tables_handler,
    ),

    # === 数据库初始化 ===
    # 初始化所有数据库
    BaseRoute(
        path="/v1/opsbffsrv/db_init/initialize",
        method=http.HTTPMethod.POST,
        handler=initialize_databases_handler,
    ),
    # 增量构建数据库
    BaseRoute(
        path="/v1/opsbffsrv/db_init/incremental",
        method=http.HTTPMethod.POST,
        handler=incremental_build_handler,
    ),
    # 获取数据库状态
    BaseRoute(
        path="/v1/opsbffsrv/db_init/status",
        method=http.HTTPMethod.GET,
        handler=get_database_status_handler,
    ),

    # === pgweb 代理 ===
    # 代理 pgweb 的 GET 请求
    BaseRoute(
        path="/v1/opsbffsrv/pgweb/{path:path}",
        method=http.HTTPMethod.GET,
        handler=pgweb_proxy_handler,
    ),
    # 代理 pgweb 的 POST 请求
    BaseRoute(
        path="/v1/opsbffsrv/pgweb/{path:path}",
        method=http.HTTPMethod.POST,
        handler=pgweb_proxy_handler,
    ),
    # 代理 pgweb 的 PUT 请求
    BaseRoute(
        path="/v1/opsbffsrv/pgweb/{path:path}",
        method=http.HTTPMethod.PUT,
        handler=pgweb_proxy_handler,
    ),
    # 代理 pgweb 的 DELETE 请求
    BaseRoute(
        path="/v1/opsbffsrv/pgweb/{path:path}",
        method=http.HTTPMethod.DELETE,
        handler=pgweb_proxy_handler,
    ),
    # 代理 pgweb 的 PATCH 请求
    BaseRoute(
        path="/v1/opsbffsrv/pgweb/{path:path}",
        method=http.HTTPMethod.PATCH,
        handler=pgweb_proxy_handler,
    ),
    # 代理 pgweb 的根路径 GET 请求
    BaseRoute(
        path="/v1/opsbffsrv/pgweb",
        method=http.HTTPMethod.GET,
        handler=pgweb_proxy_handler,
    ),

    # === redis-commander 代理 ===
    # 代理 redis-commander 的 GET 请求
    BaseRoute(
        path="/v1/opsbffsrv/redis_commander/{path:path}",
        method=http.HTTPMethod.GET,
        handler=redis_commander_proxy_handler,
    ),
    # 代理 redis-commander 的 POST 请求
    BaseRoute(
        path="/v1/opsbffsrv/redis_commander/{path:path}",
        method=http.HTTPMethod.POST,
        handler=redis_commander_proxy_handler,
    ),
    # 代理 redis-commander 的 PUT 请求
    BaseRoute(
        path="/v1/opsbffsrv/redis_commander/{path:path}",
        method=http.HTTPMethod.PUT,
        handler=redis_commander_proxy_handler,
    ),
    # 代理 redis-commander 的 DELETE 请求
    BaseRoute(
        path="/v1/opsbffsrv/redis_commander/{path:path}",
        method=http.HTTPMethod.DELETE,
        handler=redis_commander_proxy_handler,
    ),
    # 代理 redis-commander 的 PATCH 请求
    BaseRoute(
        path="/v1/opsbffsrv/redis_commander/{path:path}",
        method=http.HTTPMethod.PATCH,
        handler=redis_commander_proxy_handler,
    ),
    # 代理 redis-commander 的根路径 GET 请求
    BaseRoute(
        path="/v1/opsbffsrv/redis_commander",
        method=http.HTTPMethod.GET,
        handler=redis_commander_proxy_handler,
    ),

    # === mongo-express 代理 ===
    BaseRoute(
        path="/v1/opsbffsrv/mongo_express/{path:path}",
        method=http.HTTPMethod.GET,
        handler=mongo_express_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/mongo_express/{path:path}",
        method=http.HTTPMethod.POST,
        handler=mongo_express_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/mongo_express/{path:path}",
        method=http.HTTPMethod.PUT,
        handler=mongo_express_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/mongo_express/{path:path}",
        method=http.HTTPMethod.DELETE,
        handler=mongo_express_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/mongo_express/{path:path}",
        method=http.HTTPMethod.PATCH,
        handler=mongo_express_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/mongo_express",
        method=http.HTTPMethod.GET,
        handler=mongo_express_proxy_handler,
    ),

    # === RabbitMQ 管理代理 ===
    BaseRoute(
        path="/v1/opsbffsrv/rabbitmq_mgmt/{path:path}",
        method=http.HTTPMethod.GET,
        handler=rabbitmq_mgmt_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/rabbitmq_mgmt/{path:path}",
        method=http.HTTPMethod.POST,
        handler=rabbitmq_mgmt_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/rabbitmq_mgmt/{path:path}",
        method=http.HTTPMethod.PUT,
        handler=rabbitmq_mgmt_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/rabbitmq_mgmt/{path:path}",
        method=http.HTTPMethod.DELETE,
        handler=rabbitmq_mgmt_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/rabbitmq_mgmt/{path:path}",
        method=http.HTTPMethod.PATCH,
        handler=rabbitmq_mgmt_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/rabbitmq_mgmt",
        method=http.HTTPMethod.GET,
        handler=rabbitmq_mgmt_proxy_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/internal/health/rabbitmq_mgmt_login_bypass",
        method=http.HTTPMethod.GET,
        handler=rabbitmq_mgmt_login_bypass_probe_handler,
    ),

    # ==================== Workflow 工作流编排 / Workflow Orchestration ====================

    # 工作流定义管理 / Workflow Definition Management
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows",
        method=http.HTTPMethod.GET,
        handler=list_workflows_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/stats",
        method=http.HTTPMethod.GET,
        handler=get_workflow_stats_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}",
        method=http.HTTPMethod.GET,
        handler=get_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows",
        method=http.HTTPMethod.POST,
        handler=create_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}",
        method=http.HTTPMethod.PUT,
        handler=update_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}",
        method=http.HTTPMethod.DELETE,
        handler=delete_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/toggle",
        method=http.HTTPMethod.POST,
        handler=toggle_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/duplicate",
        method=http.HTTPMethod.POST,
        handler=duplicate_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/versions",
        method=http.HTTPMethod.GET,
        handler=list_workflow_versions_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/rollback",
        method=http.HTTPMethod.POST,
        handler=rollback_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/publish",
        method=http.HTTPMethod.POST,
        handler=publish_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/validate",
        method=http.HTTPMethod.POST,
        handler=validate_workflow_handler,
    ),

    # 工作流统计 / Workflow Statistics
    # 工作流运行管理 / Workflow Run Management
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/{id:uuid}/trigger",
        method=http.HTTPMethod.POST,
        handler=trigger_workflow_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/runs",
        method=http.HTTPMethod.GET,
        handler=list_runs_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/runs/{run_id}/graph",
        method=http.HTTPMethod.GET,
        handler=get_run_graph_status_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/alerts",
        method=http.HTTPMethod.GET,
        handler=list_workflow_alerts_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/alerts/{alert_id}/ack",
        method=http.HTTPMethod.POST,
        handler=acknowledge_workflow_alert_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/workflows/alerts/{alert_id}/resolve",
        method=http.HTTPMethod.POST,
        handler=resolve_workflow_alert_handler,
    ),
    BaseRoute(
        path="/v1/opsbffsrv/ops/runs/{run_id}/nodes/{node_id}/logs",
        method=http.HTTPMethod.GET,
        handler=get_node_history_handler,
    ),

    # === 认证管理 ===
    # 获取验证码
    BaseRoute(
        path="/v1/opsbffsrv/auth/captcha",
        method=http.HTTPMethod.GET,
        handler=get_captcha_handler,
    ),
    # 登录
    BaseRoute(
        path="/v1/opsbffsrv/auth/login",
        method=http.HTTPMethod.POST,
        handler=login_handler,
    ),
    # TOTP 绑定信息
    BaseRoute(
        path="/v1/opsbffsrv/auth/totp/setup",
        method=http.HTTPMethod.POST,
        handler=totp_setup_handler,
    ),
    # TOTP 绑定
    BaseRoute(
        path="/v1/opsbffsrv/auth/totp/bind",
        method=http.HTTPMethod.POST,
        handler=totp_bind_handler,
    ),
    # TOTP 验证
    BaseRoute(
        path="/v1/opsbffsrv/auth/totp/verify",
        method=http.HTTPMethod.POST,
        handler=totp_verify_handler,
    ),
    # 检查 session
    BaseRoute(
        path="/v1/opsbffsrv/auth/session",
        method=http.HTTPMethod.GET,
        handler=check_session_handler,
    ),
    # 登出（撤销会话）
    BaseRoute(
        path="/v1/opsbffsrv/auth/logout",
        method=http.HTTPMethod.POST,
        handler=logout_handler,
    ),
]

"""
controllersrv 路由配置

职责：
1. 操作型 API：接收请求，参数验证，任务入队，返回"执行中"
2. 查询型 API：直接查询并返回结果
3. 容器管理 API：基于 UnifiedExecutor API 的新功能
"""
import http
from linglong_web import BaseRoute
from cancan_microstack.services.controllersrv.interface.api.docker_control_api import (
    # 操作型 API
    service_start_handler,
    service_stop_handler,
    service_restart_handler,
    # 任务查询 API
    task_status_handler,
    task_list_handler,
    queue_stats_handler,
    # 服务状态查询 API
    service_status_handler,
    service_list_handler,
    container_health_handler,
    # 容器管理 API（基于 UnifiedExecutor API）
    containers_list_handler,
    container_inspect_handler,
    container_logs_handler,
    images_list_handler,
    networks_list_handler,
    volumes_list_handler,
    engine_health_handler,
)

router_list = [
    # 启动服务：接收服务名/版本等参数，任务入队执行（异步），返回任务ID用于后续查询
    BaseRoute(
        path="/v1/controllersrv/service/start",
        method=http.HTTPMethod.POST,
        handler=service_start_handler,
    ),
    # 停止服务：接收服务名/实例标识，触发停止操作，异步执行
    BaseRoute(
        path="/v1/controllersrv/service/stop",
        method=http.HTTPMethod.POST,
        handler=service_stop_handler,
    ),
    # 重启服务：对指定服务执行重启操作（stop -> start），异步执行，返回任务ID
    BaseRoute(
        path="/v1/controllersrv/service/restart",
        method=http.HTTPMethod.POST,
        handler=service_restart_handler,
    ),
    # 查询任务状态：根据任务ID返回任务当前状态与执行结果（运行中/成功/失败）
    BaseRoute(
        path="/v1/controllersrv/task/status",
        method=http.HTTPMethod.GET,
        handler=task_status_handler,
    ),
    # 列出任务：分页或按过滤条件列出任务队列中的任务或历史任务
    BaseRoute(
        path="/v1/controllersrv/task/list",
        method=http.HTTPMethod.GET,
        handler=task_list_handler,
    ),
    # 队列统计：返回任务队列的统计信息（总数、等待、运行、失败数量等）
    BaseRoute(
        path="/v1/controllersrv/queue/stats",
        method=http.HTTPMethod.GET,
        handler=queue_stats_handler,
    ),
    # 查询单个服务状态：返回服务的运行状态、实例数量、健康状况等
    BaseRoute(
        path="/v1/controllersrv/service/status",
        method=http.HTTPMethod.GET,
        handler=service_status_handler,
    ),
    # 列出所有服务：返回集群中已管理的服务列表及其简要信息
    BaseRoute(
        path="/v1/controllersrv/service/list",
        method=http.HTTPMethod.GET,
        handler=service_list_handler,
    ),
    # 容器健康检查：查询指定容器的健康信息（用于快速定位容器级别问题）
    BaseRoute(
        path="/v1/controllersrv/container/health",
        method=http.HTTPMethod.GET,
        handler=container_health_handler,
    ),
    # == 容器管理 API（基于 UnifiedExecutor API）==
    # 列出容器：使用 API Executor 列出项目的所有容器
    BaseRoute(
        path="/v1/controllersrv/containers/list",
        method=http.HTTPMethod.GET,
        handler=containers_list_handler,
    ),
    # 检查容器详情：使用 API Executor 获取容器详细信息
    BaseRoute(
        path="/v1/controllersrv/container/inspect",
        method=http.HTTPMethod.GET,
        handler=container_inspect_handler,
    ),
    # 获取容器日志：使用 API Executor 获取容器日志
    BaseRoute(
        path="/v1/controllersrv/container/logs",
        method=http.HTTPMethod.GET,
        handler=container_logs_handler,
    ),
    # 列出镜像：使用 API Executor 列出所有镜像
    BaseRoute(
        path="/v1/controllersrv/images/list",
        method=http.HTTPMethod.GET,
        handler=images_list_handler,
    ),
    # 列出网络：使用 API Executor 列出所有网络
    BaseRoute(
        path="/v1/controllersrv/networks/list",
        method=http.HTTPMethod.GET,
        handler=networks_list_handler,
    ),
    # 列出卷：使用 API Executor 列出所有卷
    BaseRoute(
        path="/v1/controllersrv/volumes/list",
        method=http.HTTPMethod.GET,
        handler=volumes_list_handler,
    ),
    # 引擎健康检查：使用 API Executor 检查引擎健康状态
    BaseRoute(
        path="/v1/controllersrv/engine/health",
        method=http.HTTPMethod.GET,
        handler=engine_health_handler,
    ),
]

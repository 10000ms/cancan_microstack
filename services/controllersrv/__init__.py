"""controllersrv - Docker Compose 控制器服务。

这是一个特殊的服务，运行在宿主机上，负责管理 Docker Compose 集群，
不需要进行服务注册、配置拉取等常规微服务操作。
"""
from cancan_microstack.runtime.overrides import extend_service_package

__path__ = extend_service_package("controllersrv", __name__, __path__)  # type: ignore[name-defined]

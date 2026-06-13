"""Stack lifecycle manager.

提供“整栈 up/down/status”的统一入口：
- controllersrv 在宿主机后台运行（daemon + pidfile）
- 其他服务通过 docker/podman compose 运行

Provide a unified stack lifecycle entry:
- controllersrv runs on host as a background daemon (pidfile-managed)
- other services run via docker/podman compose
"""
import time
import urllib.request
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..runtime.compose_cmd import run_compose_streaming
from ..runtime.host_daemon import default_daemon_paths
from ..runtime.host_daemon import start_daemon
from ..runtime.host_daemon import stop_daemon
from .microstack import CancanMicrostack


@dataclass(frozen=True)
class StackOptions:
    """整栈运行参数 / Stack runtime options."""

    workspace: Path
    service_file: Path | None
    overrides: Sequence[Path]
    output: Path | None
    bootstrap: bool
    engine: str | None

    controllersrv_host: str
    controllersrv_port: int
    with_controllersrv: bool


class StackManager:
    """整栈生命周期管理 / Stack lifecycle manager."""

    def get_controllersrv_daemon_paths(self, workspace: Path):
        """Get default daemon paths for controllersrv.

        获取 controllersrv 的默认 daemon 路径。
        """

        return default_daemon_paths(workspace, name="controllersrv")

    def __init__(self, stack: CancanMicrostack | None = None) -> None:
        self._stack = stack or CancanMicrostack()

    def build(self, options: StackOptions) -> Path:
        """生成 compose 文件 / Build compose file."""

        if options.bootstrap:
            # CLI 的 bootstrap 逻辑目前在 cli/main.py 中。
            # Here we only build compose; bootstrap happens in CLI layer.
            pass

        return self._stack.build_compose(
            workspace=options.workspace,
            service_file=options.service_file,
            overrides=options.overrides,
            output=options.output,
        )

    def start_controllersrv(self, options: StackOptions) -> int:
        """后台启动 controllersrv / Start controllersrv as host daemon."""

        paths = default_daemon_paths(options.workspace, name="controllersrv")

        argv = [
            sys.executable,
            "-m",
            "cancan_microstack.cli",
            "services",
            "run",
            "controllersrv",
            "--host",
            options.controllersrv_host,
            "--port",
            str(options.controllersrv_port),
            "--workspace",
            str(options.workspace),
        ]

        env = {}
        if options.engine:
            # Propagate engine preference into controllersrv (Dragonfly auto-detect is Docker-first).
            # 将引擎偏好传给 controllersrv（Dragonfly 的 auto-detect 是 Docker-first）。
            env["CANCAN_CONTAINER_ENGINE"] = options.engine

        return start_daemon(argv=argv, workspace=options.workspace, paths=paths, env=env)

    def wait_controllersrv_ready(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float = 8.0,
    ) -> bool:
        """Wait until controllersrv internal health is reachable.

        等待 controllersrv 的 /internal/health 可访问。
        """

        url = f"http://{host}:{port}/internal/health"
        deadline = time.time() + timeout_seconds
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1.0) as resp:
                    if 200 <= resp.status < 300:
                        return True
            except Exception as exc:
                last_error = exc
            time.sleep(0.2)

        _ = last_error
        return False

    def stop_controllersrv(self, workspace: Path) -> bool:
        """停止 controllersrv daemon / Stop controllersrv daemon."""

        paths = default_daemon_paths(workspace, name="controllersrv")
        return stop_daemon(paths=paths)

    def compose_up(
        self,
        *,
        workspace: Path,
        compose_file: Path,
        engine: str | None = None,
        build: bool = False,
    ) -> None:
        """启动容器栈 / Bring up container stack."""

        log_file = workspace / "server_log_data" / "stack" / "compose.up.log"
        args = ["up", "-d"]
        if build:
            args.append("--build")
        run_compose_streaming(
            compose_file=compose_file,
            args=args,
            workspace=workspace,
            engine=engine,
            log_file=log_file,
        )

    def compose_down(
        self,
        *,
        workspace: Path,
        compose_file: Path,
        engine: str | None = None,
        remove_volumes: bool = False,
    ) -> None:
        """关闭容器栈 / Bring down container stack."""

        args = ["down"]
        if remove_volumes:
            args.append("--volumes")

        log_file = workspace / "server_log_data" / "stack" / "compose.down.log"
        run_compose_streaming(
            compose_file=compose_file,
            args=args,
            workspace=workspace,
            engine=engine,
            log_file=log_file,
        )

    def compose_ps(self, *, workspace: Path, compose_file: Path, engine: str | None = None) -> None:
        """查看 compose 状态 / Show compose status."""

        log_file = workspace / "server_log_data" / "stack" / "compose.ps.log"
        run_compose_streaming(
            compose_file=compose_file,
            args=["ps"],
            workspace=workspace,
            engine=engine,
            log_file=log_file,
        )

"""Argparse-based CLI for Cancan Microstack."""
import argparse
import os
import time
from pathlib import Path
from typing import Sequence

from .. import __version__
from ..core.stack_manager import StackManager
from ..core.stack_manager import StackOptions
from ..core.microstack import CancanMicrostack
from . import log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cancan", description="Cancan Microstack helper commands")
    sub = parser.add_subparsers(dest="command", required=True)

    assets_parser = sub.add_parser("assets", help="Inspect packaged assets")
    assets_sub = assets_parser.add_subparsers(dest="assets_command", required=True)

    list_parser = assets_sub.add_parser("list", help="List assets")
    list_parser.add_argument("subdir", nargs="?", help="Optional asset subdirectory filter")

    export_parser = assets_sub.add_parser("export", help="Export asset to destination")
    export_parser.add_argument("logical_name", help="Asset logical name, e.g. docker/docker-compose.infra.yml")
    export_parser.add_argument("destination", help="Destination file or directory path")
    export_parser.add_argument("--overwrite", action="store_true", help="Overwrite destination when it exists")

    compose_parser = sub.add_parser("compose", help="Compose orchestration helpers")
    compose_sub = compose_parser.add_subparsers(dest="compose_command", required=True)
    build_parser = compose_sub.add_parser("build", help="Generate merged compose stack")
    build_parser.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")
    build_parser.add_argument("--service-file", help="Optional service compose file from workspace")
    build_parser.add_argument("--override", action="append", default=[], help="Additional override compose files")
    build_parser.add_argument("--output", help="Target compose file path (default: compose.cancan.yml)")
    build_parser.add_argument(
        "--bootstrap",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export missing workspace assets (infra compose, Caddy/service Dockerfiles, DDL)",
    )

    svc_parser = sub.add_parser("services", help="Run bundled services")
    svc_sub = svc_parser.add_subparsers(dest="services_command", required=True)
    run_parser = svc_sub.add_parser("run", help="Run a managed service")
    run_parser.add_argument("name", choices=["controllersrv", "infrasrv", "opsbffsrv"], help="Service name")
    run_parser.add_argument("--host", default="0.0.0.0", help="Host binding")
    run_parser.add_argument("--port", type=int, help="Port binding (defaults depend on service)")
    run_parser.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")

    sub.add_parser("version", help="Show version")

    doctor_parser = sub.add_parser("doctor", help="Diagnose environment & config readiness before stack up")
    doctor_parser.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")

    init_parser = sub.add_parser("init", help="Scaffold a minimal runnable workspace (compose sample + .env + overrides)")
    init_parser.add_argument("--workspace", default=".", help="Target workspace dir (default: current directory)")

    stack_parser = sub.add_parser("stack", help="Start/stop the whole microstack")
    stack_sub = stack_parser.add_subparsers(dest="stack_command", required=True)

    stack_up = stack_sub.add_parser("up", help="Build + bootstrap + start controllersrv + compose up")
    stack_up.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")
    stack_up.add_argument("--service-file", default="docker-compose.services.yml", help="Business compose file")
    stack_up.add_argument("--override", action="append", default=[], help="Additional override compose files")
    stack_up.add_argument("--output", help="Target compose file path (default: compose.cancan.yml)")
    stack_up.add_argument(
        "--bootstrap",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export missing workspace assets (infra compose, Caddy/service Dockerfiles, DDL, adminops)",
    )
    stack_up.add_argument(
        "--with-controllersrv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Start/ensure host controllersrv is running before bringing up containers",
    )
    stack_up.add_argument("--controllersrv-host", default="127.0.0.1", help="controllersrv bind host")
    stack_up.add_argument("--controllersrv-port", default=22100, type=int, help="controllersrv bind port")
    stack_up.add_argument(
        "--engine",
        choices=["auto", "docker", "podman"],
        default="auto",
        help="Container engine for compose command detection",
    )
    stack_up.add_argument(
        "--build",
        action="store_true",
        help="Force rebuild images (equivalent to compose up --build)",
    )

    stack_down = stack_sub.add_parser("down", help="Compose down + stop controllersrv")
    stack_down.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")
    stack_down.add_argument("--compose-file", default="compose.cancan.yml", help="Compose file to use")
    stack_down.add_argument(
        "--with-controllersrv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop host controllersrv after bringing down containers",
    )
    stack_down.add_argument(
        "--volumes",
        action="store_true",
        help="Remove named volumes when bringing stack down",
    )
    stack_down.add_argument(
        "--engine",
        choices=["auto", "docker", "podman"],
        default="auto",
        help="Container engine for compose command detection",
    )

    stack_status = stack_sub.add_parser("status", help="Show stack status (controllersrv + compose ps)")
    stack_status.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")
    stack_status.add_argument("--compose-file", default="compose.cancan.yml", help="Compose file to use")
    stack_status.add_argument(
        "--engine",
        choices=["auto", "docker", "podman"],
        default="auto",
        help="Container engine for compose command detection",
    )

    controllersrv_parser = sub.add_parser("controllersrv", help="Manage host controllersrv daemon")
    controllersrv_sub = controllersrv_parser.add_subparsers(dest="controllersrv_command", required=True)

    controllersrv_restart = controllersrv_sub.add_parser(
        "restart",
        help="Stop existing daemon (if any) and start a fresh controllersrv on the host",
    )
    controllersrv_restart.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")
    controllersrv_restart.add_argument("--host", default="127.0.0.1", help="controllersrv bind host")
    controllersrv_restart.add_argument("--port", type=int, default=22100, help="controllersrv bind port")
    controllersrv_restart.add_argument(
        "--engine",
        choices=["auto", "docker", "podman"],
        default="auto",
        help="Container engine preference propagated into controllersrv (auto = detect)",
    )
    controllersrv_restart.add_argument(
        "--wait",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Wait for /internal/health after restart (default: enabled)",
    )
    controllersrv_restart.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Seconds to wait for controllersrv health before reporting timeout",
    )

    return parser


def _write_text_if_missing(path: Path, content: str) -> None:
    """仅在文件不存在时写入内容。
    Write content only when the file does not exist.
    """

    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_env_file(workspace: Path, stack: CancanMicrostack) -> None:
    """缺失时从模板生成工作区 .env，并填入新鲜的 AUTH_TOTP_FERNET_KEY。
    Create workspace .env from the template (when missing) with a fresh TOTP encryption key.

    说明 / Note: opsbffsrv 生产模式下要求 AUTH_TOTP_FERNET_KEY 非空，否则拒绝启动；
    这里为每个工作区生成一个稳定的真实 key，既保证开箱即用，又避免共享弱默认。
    opsbffsrv refuses to start in prod mode with an empty key; we generate a real,
    per-workspace key so the stack works out of the box without a shared weak default.
    """

    env_path = workspace / ".env"
    if env_path.exists():
        return
    try:
        template = stack.assets.read_text("env/env.example")
    except Exception:
        return

    key = ""
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
    except Exception:
        key = ""

    lines = []
    for line in template.splitlines():
        if key and line.startswith("AUTH_TOTP_FERNET_KEY="):
            lines.append(f"AUTH_TOTP_FERNET_KEY={key}")
        else:
            lines.append(line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bootstrap_workspace_files(workspace: Path, stack: CancanMicrostack) -> None:
    """为 compose 运行准备工作区文件（缺失则创建）。
    Bootstrap workspace files needed to run compose (create when missing).

    目标 / Goals:
    - 在缺失时导出运行时资产到工作区：infra compose、Caddy/Service Dockerfile、DDL、adminops 前端。
      Export runtime assets into the workspace when missing: infra compose,
      Caddy/service Dockerfiles, DDL, and the adminops frontend.

    说明 / Note: 容器内服务直接以 ``python -m cancan_microstack.cmd.<svc>.run`` 运行**已安装的包**，
    不再需要工作区里的 ``cmd/*`` 包装脚本（旧布局遗留，已移除）。
    Containerized services run the installed package directly via
    ``python -m cancan_microstack.cmd.<svc>.run``; no workspace ``cmd/*`` wrappers are needed.
    """

    def _export_asset_if_missing(logical_name: str, destination: Path) -> None:
        """Export packaged assets on demand without overwriting user changes.

        按需导出打包资产，避免覆盖用户在工作区中的自定义内容。
        """

        if destination.exists():
            return
        try:
            stack.export_asset(logical_name, destination, overwrite=False)
        except FileExistsError:
            pass

    # Optional export: infra compose file for include-based docker-compose.yml.
    # 可选导出：用于 include 的 infra compose 文件（缺失才导出）。
    target_infra_file = workspace / "infra" / "docker-compose.infra.yml"
    _export_asset_if_missing("docker/docker-compose.infra.yml", target_infra_file)

    # Export base Dockerfile scaffolds for caddy + python services when missing.
    # 导出 Caddy 与 Python 服务镜像的基础脚手架（缺失时才复制）。
    _export_asset_if_missing("builds/caddy", workspace / "builds" / "caddy")
    _export_asset_if_missing("builds/service", workspace / "builds" / "service")

    # Ensure Postgres init scripts exist so compose can create logical databases on first boot.
    # 确保 PostgreSQL 初始化脚本存在，便于首次启动时创建 infra/ops/biz 数据库。
    _export_asset_if_missing("ddl/create_db.sql", workspace / "ddl" / "create_db.sql")

    # Export the env template and seed a workspace .env (with a fresh TOTP key) when missing.
    # 导出 env 模板；缺失时生成带新鲜 TOTP 密钥的工作区 .env（供 compose 注入凭据/密钥）。
    _export_asset_if_missing("env/env.example", workspace / ".env.example")
    _seed_env_file(workspace, stack)

    # Export adminops frontend into workspace for Caddy to serve.
    # 导出 adminops 前端到工作区，供 Caddy 静态挂载使用。
    target_adminops_dir = workspace / "builds" / "caddy" / "www" / "adminops"
    should_export_adminops = (not target_adminops_dir.exists())
    if target_adminops_dir.exists() and target_adminops_dir.is_dir():
        try:
            should_export_adminops = not any(target_adminops_dir.iterdir())
        except OSError:
            should_export_adminops = True

    if should_export_adminops:
        try:
            stack.export_asset("www/adminops", target_adminops_dir, overwrite=False)
        except FileExistsError:
            # Race: another process created it.
            # 竞态条件：目录被并发创建，忽略即可。
            pass


_SERVICES_COMPOSE_SAMPLE = """\
# 你的业务服务；`cancan compose build` 会把它与内置基础设施 compose 合并。
# Your business services. Merged with the bundled infra compose by `cancan compose build`.
services:
  # 示例服务 —— 替换为你自己的。Example service — replace with your own.
  app.service:
    # build: ./app          # 你的业务镜像 / your business image
    image: app_python_service:latest
    networks: [app_network]
    expose: ["8000"]
    # depends_on / environment / volumes ... 按需添加 / add as needed
"""

_OVERRIDES_README = """\
# cancan_overrides

在这里放你要替换的 cancan 内置服务文件（免 fork）。运行时会优先加载本目录。
Drop files here to override cancan's bundled services without forking; loaded with priority at runtime.

例 / Example:
    cancan_overrides/infrasrv/conf/config.py   # 只放你要改的文件 / only the files you change

也可用环境变量 CANCAN_OVERRIDE_ROOT 指定其它目录。
You can also point CANCAN_OVERRIDE_ROOT at a different directory.
"""

_WS_GITIGNORE = """\
.env
server_log_data/
compose.cancan.yml
builds/caddy/logs/
"""

_WS_README = """\
# Cancan workspace

```bash
cancan doctor        # 预检环境 / pre-flight checks
cancan stack up      # 启动整套栈 / bring the stack up
cancan stack status
cancan stack down
```

- 业务服务写在 `docker-compose.services.yml`。Business services live in `docker-compose.services.yml`.
- 配置与密钥在 `.env`（已自动生成 TOTP 加密 key；生产请修改弱默认值）。
  Config & secrets in `.env` (a TOTP key is generated for you; change weak defaults before production).
- 用 `cancan_overrides/<service>/` 免 fork 覆盖内置服务。Override bundled services via `cancan_overrides/<service>/`.
"""


def _scaffold_workspace(workspace: Path, stack: CancanMicrostack) -> None:
    """生成一个最小可跑的工作区 / Scaffold a minimal runnable workspace."""

    workspace.mkdir(parents=True, exist_ok=True)
    # 复用同一套资产 bootstrap（infra compose / Caddy·service Dockerfile / ddl / adminops / .env）。
    # Reuse the same asset bootstrap.
    _bootstrap_workspace_files(workspace, stack)
    # 仅 scaffold 才生成的文件 / scaffold-only files.
    _write_text_if_missing(workspace / "docker-compose.services.yml", _SERVICES_COMPOSE_SAMPLE)
    _write_text_if_missing(workspace / "cancan_overrides" / "README.md", _OVERRIDES_README)
    _write_text_if_missing(workspace / ".gitignore", _WS_GITIGNORE)
    _write_text_if_missing(workspace / "README.md", _WS_README)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    # The service container image installs `cancan-microstack==${CANCAN_VERSION}`,
    # so expose the package version to every compose subprocess. setdefault keeps
    # an explicit user override (e.g. building a different/dev version) intact.
    os.environ.setdefault("CANCAN_VERSION", __version__)

    stack = CancanMicrostack()
    stack_manager = StackManager(stack)

    if args.command == "assets":
        if args.assets_command == "list":
            records = stack.assets.list_assets(args.subdir)
            for record in records:
                log("asset", name=record.logical_name, path=record.path, is_dir=record.is_dir)
            return 0
        if args.assets_command == "export":
            destination = Path(args.destination).expanduser().resolve()
            stack.export_asset(args.logical_name, destination, overwrite=args.overwrite)
            return 0

    if args.command == "compose" and args.compose_command == "build":
        workspace = Path(args.workspace).expanduser().resolve()
        service_file = Path(args.service_file).resolve() if args.service_file else None
        overrides = [Path(item).expanduser().resolve() for item in args.override]
        output = Path(args.output).expanduser().resolve() if args.output else None
        if args.bootstrap:
            _bootstrap_workspace_files(workspace, stack)
        stack.build_compose(workspace=workspace, service_file=service_file, overrides=overrides, output=output)
        log("compose written", path=output or workspace / "compose.cancan.yml")
        return 0

    if args.command == "stack":
        if args.stack_command == "up":
            workspace = Path(args.workspace).expanduser().resolve()
            service_file = Path(args.service_file).expanduser().resolve() if args.service_file else None
            overrides = [Path(item).expanduser().resolve() for item in args.override]
            output = Path(args.output).expanduser().resolve() if args.output else None

            if args.bootstrap:
                _bootstrap_workspace_files(workspace, stack)

            start_time = time.perf_counter()

            def _step(msg: str) -> float:
                now = time.perf_counter()
                elapsed = now - start_time
                print(f"[stack] +{elapsed:0.2f}s {msg}")
                return now

            _step(f"workspace={workspace}")

            options = StackOptions(
                workspace=workspace,
                service_file=service_file,
                overrides=overrides,
                output=output,
                bootstrap=args.bootstrap,
                engine=(None if args.engine == "auto" else args.engine),
                controllersrv_host=args.controllersrv_host,
                controllersrv_port=args.controllersrv_port,
                with_controllersrv=args.with_controllersrv,
            )

            compose_file = stack_manager.build(options)
            if options.with_controllersrv:
                _step(f"start controllersrv (engine={options.engine or 'auto'})")
                pid = stack_manager.start_controllersrv(options)
                log("controllersrv", status="running", pid=pid, host=options.controllersrv_host,
                    port=options.controllersrv_port)
                paths = stack_manager.get_controllersrv_daemon_paths(workspace)
                print(f"[stack] controllersrv pid={pid} log={paths.log_file} pidfile={paths.pid_file}")

                _step("wait controllersrv /internal/health")
                ready = stack_manager.wait_controllersrv_ready(
                    host=options.controllersrv_host,
                    port=options.controllersrv_port,
                    timeout_seconds=8.0,
                )
                if not ready:
                    print(
                        "[stack] WARNING: controllersrv health not ready yet. "
                        "If startup is slow, check its log: "
                        f"{paths.log_file}"
                    )

            _step(f"compose up -d{' --build' if args.build else ''} (engine={options.engine or 'auto'})")
            print(f"[stack] compose logs -> {workspace / 'server_log_data' / 'stack' / 'compose.up.log'}")
            stack_manager.compose_up(
                workspace=workspace,
                compose_file=compose_file,
                engine=options.engine,
                build=args.build,
            )
            _step("done")
            log("stack", status="up", compose_file=compose_file)
            return 0

        if args.stack_command == "down":
            workspace = Path(args.workspace).expanduser().resolve()
            compose_file = Path(args.compose_file).expanduser().resolve()
            engine = None if args.engine == "auto" else args.engine

            stack_manager.compose_down(
                workspace=workspace,
                compose_file=compose_file,
                engine=engine,
                remove_volumes=args.volumes,
            )
            if args.with_controllersrv:
                stopped = stack_manager.stop_controllersrv(workspace)
                log("controllersrv", status=("stopped" if stopped else "not_running"))
            log("stack", status="down")
            return 0

        if args.stack_command == "status":
            workspace = Path(args.workspace).expanduser().resolve()
            compose_file = Path(args.compose_file).expanduser().resolve()
            engine = None if args.engine == "auto" else args.engine

            # controllersrv status via pidfile
            from ..runtime.host_daemon import default_daemon_paths
            from ..runtime.host_daemon import read_pid

            paths = default_daemon_paths(workspace, name="controllersrv")
            pid = read_pid(paths.pid_file)
            log("controllersrv", pid=pid, pid_file=str(paths.pid_file))
            stack_manager.compose_ps(workspace=workspace, compose_file=compose_file, engine=engine)
            return 0

    if args.command == "controllersrv":
        workspace = Path(args.workspace).expanduser().resolve()
        engine = None if args.engine == "auto" else args.engine
        options = StackOptions(
            workspace=workspace,
            service_file=None,
            overrides=[],
            output=None,
            bootstrap=False,
            engine=engine,
            controllersrv_host=args.host,
            controllersrv_port=args.port,
            with_controllersrv=True,
        )

        if args.controllersrv_command == "restart":
            stopped = stack_manager.stop_controllersrv(workspace)
            log(
                "controllersrv",
                action="stop",
                status=("stopped" if stopped else "not_running"),
                workspace=str(workspace),
            )
            pid = stack_manager.start_controllersrv(options)
            log(
                "controllersrv",
                action="start",
                status="running",
                pid=pid,
                host=options.controllersrv_host,
                port=options.controllersrv_port,
                engine=options.engine or "auto",
            )
            if args.wait:
                ready = stack_manager.wait_controllersrv_ready(
                    host=options.controllersrv_host,
                    port=options.controllersrv_port,
                    timeout_seconds=args.timeout,
                )
                log(
                    "controllersrv",
                    action="wait_health",
                    status=("ready" if ready else "timeout"),
                    timeout=args.timeout,
                )
                if not ready:
                    print(
                        "[controllersrv] WARNING: health check timeout; "
                        "inspect daemon logs if startup takes longer than expected."
                    )
            return 0

    if args.command == "services" and args.services_command == "run":
        workspace = Path(args.workspace).expanduser().resolve()
        default_ports = {
            "controllersrv": 22100,
            "infrasrv": 8080,
            "opsbffsrv": 8080,
        }
        stack.run_service(
            args.name,
            host=args.host,
            port=(args.port if args.port is not None else default_ports[args.name]),
            workspace=workspace,
        )
        return 0

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "doctor":
        from ..core.doctor import run_doctor

        workspace = Path(args.workspace).expanduser().resolve()
        return run_doctor(workspace)

    if args.command == "init":
        workspace = Path(args.workspace).expanduser().resolve()
        _scaffold_workspace(workspace, stack)
        log("init", workspace=str(workspace), status="ready", next="cancan doctor && cancan stack up")
        return 0

    parser.error("Unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

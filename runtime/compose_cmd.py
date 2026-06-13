"""Compose command detection & execution helpers.

提供对 Docker/Podman Compose 的自动探测与执行。
Provide auto-detection and execution helpers for Docker/Podman compose commands.

Notes:
- 用户不需要手动运行 `docker compose` / `podman compose`；cancan CLI 会在内部调用。
  Users don't need to run `docker compose` / `podman compose` manually; cancan CLI will call it internally.
- 本模块只依赖标准库，便于未来抽离成独立包。
  This module uses stdlib only, so it can be extracted into a standalone package later.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from typing import IO
from typing import Iterable


@dataclass(frozen=True)
class ComposeCommand:
    """Compose 命令描述 / Compose command descriptor."""

    argv_prefix: list[str]

    def with_file(self, compose_file: Path) -> list[str]:
        return [*self.argv_prefix, "-f", str(compose_file)]


def _can_run(
    cmd: list[str],
    runner: Callable[..., subprocess.CompletedProcess[str]],
    *,
    timeout_seconds: float = 5.0,
) -> bool:
    """轻量检测命令是否可运行 / Lightweight check whether a command can run."""

    try:
        result = runner(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except Exception:
        return False

    return result.returncode == 0


def _first_existing(which: Callable[[str], str | None], names: Iterable[str]) -> str | None:
    for name in names:
        if which(name):
            return name
    return None


def _daemon_ready_probe(prefix: list[str]) -> list[str] | None:
    """Return a probe command that validates the engine daemon is reachable.

    返回用于验证引擎 daemon 可用的 probe 命令。

    Notes:
    - `docker compose version` 只验证 CLI 存在，不保证 Docker daemon 可用。
      `docker compose version` only checks CLI presence, not Docker daemon readiness.
    - `podman compose version` 同理。
      Same for podman.
    """

    if prefix[:2] == ["docker", "compose"] or prefix == ["docker-compose"]:
        return ["docker", "info"]
    if prefix[:2] == ["podman", "compose"] or prefix == ["podman-compose"]:
        return ["podman", "info"]
    return None


def detect_compose_command(
        *,
        engine: str | None = None,
        which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ComposeCommand:
    """自动探测 Compose 命令（Docker 或 Podman）。

    Auto-detect compose command (Docker or Podman).

    Args:
        engine: "docker" | "podman" | "auto" | None.
            - None/"auto": try docker first then podman
            - "docker": docker only
            - "podman": podman only
        which: injectable for tests.
        runner: injectable for tests.

    Returns:
        ComposeCommand: argv prefix, e.g. ["docker", "compose"] or ["podman-compose"].

    Raises:
        RuntimeError: when no supported compose command is found.
    """

    normalized = (engine or os.environ.get("CANCAN_CONTAINER_ENGINE") or "auto").strip().lower()
    if normalized not in {"auto", "docker", "podman"}:
        normalized = "auto"

    candidates: list[list[str]] = []

    def add_docker_candidates() -> None:
        # Prefer `docker compose` when docker exists.
        # 优先使用 `docker compose`。
        if which("docker"):
            candidates.append(["docker", "compose"])
        if which("docker-compose"):
            candidates.append(["docker-compose"])

    def add_podman_candidates() -> None:
        # Prefer `podman compose` (Podman v4+ plugin). It avoids podman-compose pod semantics.
        # 优先使用 `podman compose`（Podman v4+ 插件），避免 podman-compose 的 pod 语义与噪声报错。
        if which("podman"):
            candidates.append(["podman", "compose"])
        if which("podman-compose"):
            candidates.append(["podman-compose"])

    if normalized == "docker":
        add_docker_candidates()
    elif normalized == "podman":
        add_podman_candidates()
    else:
        # Auto mode: try Docker first only if Docker daemon is reachable; otherwise prefer Podman.
        # 自动模式：只有当 Docker daemon 可用时才优先 Docker；否则优先 Podman，避免卡住。
        add_docker_candidates()
        add_podman_candidates()

    for prefix in candidates:
        # 1) CLI exists?
        # 1) CLI 是否存在？
        if not _can_run([*prefix, "version"], runner, timeout_seconds=5.0):
            continue

        # 2) Daemon reachable? (best-effort, fast timeout)
        # 2) daemon 是否可用？（尽力而为，短超时）
        probe = _daemon_ready_probe(prefix)
        if probe is not None and _can_run(probe, runner, timeout_seconds=2.0):
            return ComposeCommand(argv_prefix=prefix)

        # If probe is not available, accept CLI presence.
        # 若没有 probe，退化为“CLI 存在即接受”。
        if probe is None:
            return ComposeCommand(argv_prefix=prefix)

    # Fallback: if some CLI exists but daemon probe failed (e.g. engine booting), return first CLI.
    # 兜底：若 CLI 存在但 daemon probe 失败（例如引擎刚启动），返回第一个可用 CLI。
    for prefix in candidates:
        if _can_run([*prefix, "version"], runner, timeout_seconds=5.0):
            return ComposeCommand(argv_prefix=prefix)

    raise RuntimeError(
        "No compose command found. Install Docker Desktop (docker compose) or Podman (podman compose / podman-compose)."
    )


def run_compose(
        *,
        compose_file: Path,
        args: list[str],
        workspace: Path,
        engine: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """执行 compose 子命令 / Execute compose subcommand."""

    cmd = detect_compose_command(engine=engine).with_file(compose_file)
    full_cmd = [*cmd, *args]

    runner(
        full_cmd,
        cwd=str(workspace),
        check=True,
        text=True,
    )


def run_compose_streaming(
        *,
        compose_file: Path,
        args: list[str],
        workspace: Path,
        engine: str | None = None,
        log_file: Path | None = None,
) -> None:
    """Run compose command and stream output to stdout while teeing to a log file.

    执行 compose 命令，输出实时显示在终端，同时写入日志文件。
    """

    cmd = detect_compose_command(engine=engine).with_file(compose_file)
    full_cmd = [*cmd, *args]

    log_fp: IO[str] | None = None
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_fp = open(log_file, "a", encoding="utf-8")

    try:
        proc = subprocess.Popen(
            full_cmd,
            cwd=str(workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            if log_fp is not None:
                log_fp.write(line)
        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, full_cmd)
    finally:
        if log_fp is not None:
            log_fp.close()

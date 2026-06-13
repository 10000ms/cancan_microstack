"""Host-side daemon helpers for services like controllersrv.

用于在宿主机后台启动/停止 controllersrv，并使用 pidfile 进行管理。
Start/stop host-side services (e.g. controllersrv) in background using a pidfile.

Design goals / 设计目标:
- 标准库实现，避免引入额外依赖
  Stdio-only to avoid extra dependencies.
- 默认不覆盖用户已有进程/日志
  Do not overwrite user's existing processes/logs by default.
"""
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DaemonPaths:
    """pid/log 路径约定 / pid/log path convention."""

    pid_file: Path
    log_file: Path


def _proc_identity(pid: int) -> dict | None:
    """读取进程身份信息（启动时间 / 命令行），用于防止 PID 复用误杀。

    Read process identity (start time / cmdline) to guard against PID-reuse mis-kill.

    仅依赖标准库，尽力而为；任何一项拿不到就置 None（向后兼容、降级）。
    Stdlib-only and best-effort; any missing field is set to None (backward-compatible degradation).

    Returns:
        身份字典；若进程不存在则返回 None / identity dict, or None if the process does not exist.
    """

    try:
        # ps 在 macOS / Linux 上都可用，输出进程启动时间与命令行。
        # ps is available on both macOS and Linux; emits process start time and command line.
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to read process identity for pid=%s: %s", pid, exc)
        return None

    if out.returncode != 0:
        # 进程不存在 / process not found.
        return None

    line = out.stdout.strip()
    if not line:
        return None

    # lstart 是固定 5 字段格式（如 "Mon Jun 14 10:00:00 2026"），其后是 command。
    # lstart is a fixed 5-field format (e.g. "Mon Jun 14 10:00:00 2026"), followed by command.
    parts = line.split(maxsplit=5)
    if len(parts) >= 5:
        lstart = " ".join(parts[:5])
        cmdline = parts[5] if len(parts) == 6 else ""
        return {"lstart": lstart, "cmdline": cmdline}

    return {"lstart": line, "cmdline": ""}


def default_daemon_paths(workspace: Path, *, name: str) -> DaemonPaths:
    """计算默认 pid/log 路径 / Compute default pid/log paths."""

    pid_dir = workspace / "server_log_data" / "pids"
    pid_file = pid_dir / f"{name}.pid"
    log_file = workspace / "server_log_data" / f"{name}.out.log"
    return DaemonPaths(pid_file=pid_file, log_file=log_file)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_alive_as_recorded(pid: int, recorded_identity: dict | None) -> bool:
    """判断 pid 是否仍是当初记录的那个进程，避免 PID 复用误杀。

    Decide whether pid is still the originally-recorded process, to avoid PID-reuse mis-kill.

    向后兼容：旧 pidfile 无身份信息（recorded_identity is None）时降级为仅 os.kill(pid, 0)。
    Backward-compatible: when the old pidfile carries no identity info (recorded_identity is None),
    degrade to the legacy os.kill(pid, 0) behavior.
    """

    if not _pid_alive(pid):
        return False

    # 旧 pidfile：无身份信息，降级为旧行为。
    # Old pidfile: no identity info, degrade to legacy behavior.
    if not recorded_identity:
        return True

    actual = _proc_identity(pid)
    if actual is None:
        # 拿不到当前身份（进程刚退出或 ps 不可用）：保守按"非同一进程"处理，避免误杀。
        # Cannot read current identity (process just exited or ps unavailable):
        # conservatively treat as "not the same process" to avoid mis-kill.
        return False

    same = (
        actual.get("lstart") == recorded_identity.get("lstart")
        and actual.get("cmdline") == recorded_identity.get("cmdline")
    )
    if not same:
        log.warning(
            "PID %s reused by a different process (recorded=%s, actual=%s); not treating as alive",
            pid,
            recorded_identity,
            actual,
        )
    return same


def read_pid_record(pid_file: Path) -> tuple[int, dict | None] | None:
    """读取 pidfile 的完整记录（pid + 身份信息）。

    Read the full pidfile record (pid + identity info).

    支持两种格式 / Supports two formats:
    - 新格式 / new: JSON {"pid": int, "lstart": str, "cmdline": str}
    - 旧格式 / legacy: 纯整数文本（身份信息返回 None，降级为旧行为）
      plain integer text (identity returned as None, degrades to legacy behavior)

    Returns:
        (pid, identity_or_None)；无法读取时返回 None / (pid, identity_or_None), or None if unreadable.
    """

    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return None

    if not raw:
        return None

    # 先尝试新格式（JSON）。/ Try the new (JSON) format first.
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "pid" in data:
            pid = int(data["pid"])
            identity = {
                "lstart": data.get("lstart"),
                "cmdline": data.get("cmdline"),
            }
            # 身份字段都缺失则视为无身份信息（降级）。
            # If all identity fields are missing, treat as no identity info (degrade).
            if identity["lstart"] is None and identity["cmdline"] is None:
                identity = None
            return pid, identity
    except (ValueError, TypeError):
        pass

    # 回退到旧格式：纯整数。/ Fall back to legacy format: plain integer.
    try:
        return int(raw), None
    except ValueError:
        return None


def read_pid(pid_file: Path) -> int | None:
    """读取 pidfile 中的 pid（兼容新旧格式）/ Read the pid from the pidfile (both formats)."""

    record = read_pid_record(pid_file)
    if record is None:
        return None
    return record[0]


def start_daemon(
        *,
        argv: list[str],
        workspace: Path,
        paths: DaemonPaths,
        env: dict[str, str] | None = None,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> int:
    """后台启动进程并写 pidfile。

    Start process in background and write pidfile.

    Returns:
        pid
    """

    # 用身份校验判断已有进程是否真的还活着，避免 PID 复用把无关进程当作存活而拒绝启动。
    # Use identity-aware liveness so a reused PID (an unrelated process) is not mistaken as alive.
    existing_record = read_pid_record(paths.pid_file)
    if existing_record is not None:
        existing_pid, existing_identity = existing_record
        if existing_pid and _pid_alive_as_recorded(existing_pid, existing_identity):
            return existing_pid

    paths.pid_file.parent.mkdir(parents=True, exist_ok=True)
    paths.log_file.parent.mkdir(parents=True, exist_ok=True)

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    # Append to log file, do not truncate.
    # 追加日志，避免覆盖。
    log_fp = open(paths.log_file, "a", encoding="utf-8")
    try:
        proc = popen(
            argv,
            cwd=str(workspace),
            stdout=log_fp,
            stderr=log_fp,
            start_new_session=True,
            env=merged_env,
            text=True,
        )
    finally:
        # child keeps the fd; safe to close in parent.
        # 子进程会继承 fd；父进程关闭即可。
        log_fp.close()

    # Give it a brief moment to fail fast.
    # 短暂等待以便“快速失败”。
    time.sleep(0.2)
    if proc.poll() is not None:
        raise RuntimeError(f"Failed to start daemon: exited with code {proc.returncode}")

    # 不仅靠"没退出"判成功：再确认该 pid 当前确实是一个存活进程，并抓取其身份信息写入 pidfile。
    # Don't rely only on "didn't exit": confirm the pid is a live process now and capture its
    # identity to persist into the pidfile.
    if not _pid_alive(proc.pid):
        raise RuntimeError(f"Failed to start daemon: pid {proc.pid} not alive after launch")

    identity = _proc_identity(proc.pid)
    record: dict = {"pid": proc.pid}
    if identity:
        record.update(identity)
    else:
        # 拿不到身份信息（如 ps 不可用）：写入纯 pid，仍然向后兼容（判活时降级为旧行为）。
        # No identity available (e.g. ps unavailable): write plain pid, still backward-compatible
        # (liveness check degrades to legacy behavior).
        log.warning("Could not capture process identity for pid=%s; pidfile will use legacy format", proc.pid)

    paths.pid_file.write_text(json.dumps(record), encoding="utf-8")
    return proc.pid


def stop_daemon(
        *,
        paths: DaemonPaths,
        timeout_seconds: float = 5.0,
        remover: Callable[[Path], None] | None = None,
) -> bool:
    """停止后台进程（SIGTERM -> SIGKILL）。

    Stop daemon process (SIGTERM then SIGKILL).

    Returns:
        True if a process was stopped, False if pidfile missing/dead.
    """

    record = read_pid_record(paths.pid_file)
    if record is None:
        return False

    pid, identity = record
    if not pid:
        return False

    # 身份校验：若该 pid 已被复用为其它进程（或已死），不要向它发信号，避免误杀无关进程。
    # Identity check: if the pid has been reused by another process (or is dead), do not signal
    # it, to avoid killing an unrelated process.
    if not _pid_alive_as_recorded(pid, identity):
        try:
            paths.pid_file.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to remove stale pidfile %s: %s", paths.pid_file, exc)
        return False

    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.1)

    if _pid_alive(pid):
        os.kill(pid, signal.SIGKILL)

    try:
        paths.pid_file.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to remove pidfile %s after stop: %s", paths.pid_file, exc)

    if remover:
        try:
            remover(paths.pid_file)
        except Exception as exc:  # noqa: BLE001
            log.warning("pidfile remover callback failed for %s: %s", paths.pid_file, exc)

    return True

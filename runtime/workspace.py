"""Workspace detection helpers for Cancan Microstack.

用于在宿主项目中自动定位工作目录，并提供 server_log_data 等通用路径。
Detect workspace roots in host projects and provision common paths like server_log_data.
"""
import os
from pathlib import Path
from typing import Optional

_WORKSPACE_ENV = "CANCAN_WORKSPACE_ROOT"
_LOG_DIR_NAME = "server_log_data"
_MARKERS: tuple[str, ...] = (
    "server_log_data",
    "cmd",
    "docker-compose.infra.yml",
    "docker-compose.services.yml",
    "pyproject.toml",
    "requirements.txt",
)

_workspace_root: Optional[Path] = None


def configure_workspace(root: Path | str | None = None) -> Path:
    """配置或重新配置当前 workspace 根。

    设置当前 Cancan 工作目录，可显式传入路径，也可依赖自动探测。
    Configure the current Cancan workspace root (explicit or auto-detected).
    """

    global _workspace_root
    if isinstance(root, str):
        root_path = Path(root)
    elif root is None:
        root_path = detect_workspace_root()
    else:
        root_path = root

    _workspace_root = root_path.resolve()
    os.environ[_WORKSPACE_ENV] = str(_workspace_root)
    return _workspace_root


def get_workspace_root() -> Path:
    """返回已配置的 workspace 根；若未配置则懒加载探测。

    Return configured workspace root, lazily detecting when absent.
    """

    if _workspace_root is not None:
        return _workspace_root
    return configure_workspace(os.environ.get(_WORKSPACE_ENV))


def detect_workspace_root(start: Path | str | None = None) -> Path:
    """探测 workspace 根（环境变量优先，其次向上遍历寻找标记）。

    Detect workspace root using env var or upward marker walk.
    """

    env_value = os.environ.get(_WORKSPACE_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()

    start_path = Path(start or Path.cwd()).resolve()
    for candidate in [start_path, *start_path.parents]:
        if _has_markers(candidate):
            return candidate
    return start_path


def ensure_server_log_dir() -> Path:
    """确保标准日志目录存在 / Ensure canonical ``server_log_data`` exists."""

    root = get_workspace_root()
    log_dir = root / _LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def ensure_subdir(relative_path: str) -> Path:
    """确保 workspace 下子目录存在并返回路径 / Ensure subdir exists under workspace."""

    root = get_workspace_root()
    target = root / relative_path
    target.mkdir(parents=True, exist_ok=True)
    return target


def _has_markers(candidate: Path) -> bool:
    for marker in _MARKERS:
        if (candidate / marker).exists():
            return True
    return False

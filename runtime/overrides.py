"""Optional override support for Cancan-managed services.

允许业务仓库通过 ``cancan_overrides`` 目录注入 controllersrv / infrasrv /
opsbffsrv 的自定义配置，而无需 fork 主库。
Optional overrides so downstream workspaces can inject custom files without forking.
"""
import os
import pkgutil
from pathlib import Path
from typing import (
    Iterable,
    List,
    Optional,
)

from cancan_microstack.public.const.overrides_consts import (
    OVERRIDE_DIR_NAME,
    OVERRIDE_ENV,
)

from .workspace import configure_workspace, get_workspace_root

_override_root: Optional[Path] = None


def configure_overrides(root: Path | str | None = None) -> Optional[Path]:
    """显式设置 overrides 根目录（None 时自动探测）。

    Explicitly set override root; auto-discover when None.
    """

    global _override_root
    if isinstance(root, str):
        override_path = Path(root)
    elif root is None:
        override_path = discover_override_root()
    else:
        override_path = root

    if not override_path:
        _override_root = None
        return None

    resolved = override_path.resolve()
    if not resolved.exists():
        return None
    _override_root = resolved
    os.environ[OVERRIDE_ENV] = str(resolved)
    return resolved


def discover_override_root(start: Path | None = None) -> Optional[Path]:
    """从 workspace 起向上寻找 ``cancan_overrides`` 目录 / Search upward for overrides folder."""

    env_value = os.environ.get(OVERRIDE_ENV)
    if env_value:
        candidate = Path(env_value).expanduser().resolve()
        if candidate.exists():
            return candidate

    workspace = start or get_workspace_root()
    for candidate in [workspace, *workspace.parents]:
        override_dir = candidate / OVERRIDE_DIR_NAME
        if override_dir.exists():
            return override_dir
    return None


def get_override_root() -> Optional[Path]:
    """返回当前 overrides 根目录（若存在）/ Return current override root when configured."""

    if _override_root is not None:
        return _override_root
    return configure_overrides(os.environ.get(OVERRIDE_ENV))


def extend_service_package(service_name: str, package_name: str, package_path: Iterable[str]) -> List[str]:
    """扩展 cancan_microstack.services 的搜索路径以支持 overrides。

    If ``cancan_overrides/<service_name>`` exists, prepend it to module search path
    so workspace files override packaged ones.
    """

    override_root = get_override_root()
    if not override_root:
        return list(package_path)

    service_override = override_root / service_name
    if not service_override.exists():
        return list(package_path)

    combined_paths = [str(service_override), *package_path]
    return list(pkgutil.extend_path(combined_paths, package_name))


def bootstrap_from_workspace(workspace: Path | None) -> None:
    """在启动前同时配置 workspace 与 overrides。

    Ensure workspace and overrides are configured together before startup.
    """

    effective_root = configure_workspace(workspace)
    configure_overrides(discover_override_root(effective_root))

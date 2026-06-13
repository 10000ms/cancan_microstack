"""Helpers for resolving workspace overrides vs packaged assets.

工作区文件优先，包内资产兜底。
Prefer workspace files; fall back to packaged assets when missing.
"""
from pathlib import Path

from cancan_microstack.core.assets import AssetManager

from .workspace import get_workspace_root

_asset_manager = AssetManager()


def resolve_workspace_or_asset(relative_path: str, asset_logical: str) -> Path:
    """工作区路径优先，缺失时使用包资产。

    Prefer workspace-relative path; fall back to packaged asset when missing.
    """

    workspace_root = get_workspace_root()
    candidate = workspace_root / relative_path
    if candidate.exists():
        return candidate
    return _asset_manager.resolve_path(asset_logical)

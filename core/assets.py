"""Asset loading helpers for Cancan Microstack.

资产加载与导出工具，确保包内资源可以安全复制到工作区后再被 Docker 使用。
Asset loading/export helpers that materialize packaged resources into the caller's workspace
so Docker (which only sees mounted paths) can read them.
"""
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import (
    Iterable,
    List,
)


@dataclass(frozen=True)
class AssetRecord:
    """描述存储在包中的静态资产 / Describe packaged static asset."""

    logical_name: str
    path: Path
    is_dir: bool


class AssetManager:
    """资产管理：枚举、导出、解析包内静态文件。

    Asset management facade to list, export, and resolve packaged static files.
    """

    def __init__(self, package: str = "cancan_microstack.assets") -> None:
        self._package = package

    def list_assets(self, subdir: str | None = None) -> List[AssetRecord]:
        """列出可用资产（可选限定子目录）/ List available assets (optional subdir filter)."""

        # 重要：不要用 resources.as_file(...) 的路径来反推 logical_name。
        # 因为当资源来自 zip/轮子时，不同节点可能被物化到不同的临时目录，
        # 这会导致 relative_to 失败，从而丢失前缀（例如返回 "infra" 而不是 "ddl/infra"）。
        # Important: do NOT derive logical_name from as_file(...) paths.
        # When packaged (zip/wheel), each node may be materialized into a different temp dir,
        # making relative_to() fail and losing prefixes.
        traversable = resources.files(self._package)
        prefix = ""
        if subdir:
            prefix = "/".join(self._split(subdir))
            traversable = traversable.joinpath(*self._split(subdir))
        records: List[AssetRecord] = []

        def _walk(node, current_prefix: str) -> None:
            for child in node.iterdir():
                if child.name.startswith("__pycache__") or child.name == ".DS_Store":
                    continue
                logical_name = f"{current_prefix}/{child.name}" if current_prefix else child.name
                with resources.as_file(child) as located:
                    path = Path(located)
                    records.append(
                        AssetRecord(
                            logical_name=logical_name,
                            path=path,
                            is_dir=path.is_dir(),
                        )
                    )
                    if child.is_dir():
                        _walk(child, logical_name)

        _walk(traversable, prefix)
        return records

    def export_asset(self, logical_name: str, destination: Path, overwrite: bool = False) -> Path:
        """导出资产到工作区路径；目录用 copytree，文件用 copy2。

        Export asset into a workspace path so Docker can see it via bind/volume mounts.
        Directories use ``shutil.copytree``; files use ``shutil.copy2``.
        """

        traversable = resources.files(self._package).joinpath(*self._split(logical_name))
        if not traversable.exists():  # pragma: no cover - defensive guard
            raise FileNotFoundError(f"Asset '{logical_name}' not found")

        with resources.as_file(traversable) as asset_path:
            resolved = Path(asset_path)
            if resolved.is_dir():
                if destination.exists():
                    if not overwrite:
                        raise FileExistsError(destination)
                    shutil.rmtree(destination)
                shutil.copytree(resolved, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and not overwrite:
                    raise FileExistsError(destination)
                shutil.copy2(resolved, destination)
        return destination

    def read_text(self, logical_name: str) -> str:
        """读取资产文本 / Read text content from asset."""

        traversable = resources.files(self._package).joinpath(*self._split(logical_name))
        return traversable.read_text(encoding="utf-8")

    def resolve_path(self, logical_name: str) -> Path:
        """将资产实体化为可访问的文件路径 / Materialize and return a filesystem path."""

        traversable = resources.files(self._package).joinpath(*self._split(logical_name))
        if not traversable.exists():
            raise FileNotFoundError(logical_name)
        with resources.as_file(traversable) as asset_path:
            return Path(asset_path)

    def _split(self, logical_name: str) -> Iterable[str]:
        return [segment for segment in logical_name.split('/') if segment]

    def _logical_name(self, path: Path) -> str:
        base = resources.files(self._package)
        with resources.as_file(base) as root_path:
            root = Path(root_path)
            try:
                rel = path.relative_to(root)
            except ValueError:  # pragma: no cover - fallback for zipped resources
                return path.name
            return str(rel)

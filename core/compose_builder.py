"""Compose stack builder merging infra assets with service overlays.

把内置 infra compose 与业务/覆盖文件进行深度合并，生成最终可运行的栈。
Deep-merge infra compose with service/override files to produce a runnable stack.
"""
import copy
import sys
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Sequence,
)

import yaml

from .assets import AssetManager


class ComposeBuilder:
    """合并内置 infra compose 与工作区覆盖层 / Merge infra compose with workspace overlays."""

    def __init__(self, asset_manager: AssetManager | None = None,
                 base_asset: str = "docker/docker-compose.infra.yml") -> None:
        self.asset_manager = asset_manager or AssetManager()
        self.base_asset = base_asset

    def build(
            self,
            *,
            workspace: Path,
            service_file: Path | None = None,
            overrides: Sequence[Path] | None = None,
            output_file: Path | None = None,
    ) -> Path:
        """生成合并后的 docker compose 文件 / Generate merged docker compose file."""

        workspace = workspace.expanduser().resolve()
        output_path = (output_file or workspace / "compose.cancan.yml").resolve()
        overrides = overrides or []

        base_model = self._load_asset_yaml(self.base_asset)
        merged = base_model
        if service_file:
            if service_file.exists():
                merged = self._deep_merge(merged, self._load_yaml(service_file))
            else:
                # 不静默丢弃：业务服务文件缺失会让生成的栈只有基础设施、没有应用服务。
                # Never drop silently: a missing service file yields an infra-only stack (no app services).
                print(
                    f"[cancan] WARNING: service file not found, generated stack will have NO business "
                    f"services: {service_file}",
                    file=sys.stderr,
                )

        for override in overrides:
            if override.exists():
                merged = self._deep_merge(merged, self._load_yaml(override))

        # Docker Compose V2 ignores the deprecated `version` field and warns.
        # Docker Compose V2 会忽略已弃用的 `version` 字段并产生警告，因此统一移除。
        merged.pop("version", None)

        # Avoid network name collisions with pre-existing networks that were not created by Compose.
        # If a network is not marked as external, letting Compose generate a project-scoped name is safer.
        # 避免与历史遗留网络（非 compose 创建，缺少 label）发生冲突。
        # 若网络不是 external，则移除固定 name，让 compose 自动生成项目级网络名。
        networks = merged.get("networks")
        if isinstance(networks, dict):
            for _, net_cfg in networks.items():
                if isinstance(net_cfg, dict) and not net_cfg.get("external"):
                    net_cfg.pop("name", None)

        # When a service has a build definition, prefer local build and do not pull the image.
        # 对于带 build 的服务，默认使用本地构建，避免先去 pull 同名镜像。
        services = merged.get("services")
        if isinstance(services, dict):
            for _, svc_cfg in services.items():
                if isinstance(svc_cfg, dict) and "build" in svc_cfg:
                    svc_cfg.setdefault("pull_policy", "never")

        # 给 CANCAN_VERSION 构建参数烤入默认值（= 当前包版本），让生成的 compose 自给自足：
        # 即便不经 `cancan stack up`、直接 `docker/podman compose up` 也能成功插值，无需手动设环境变量。
        # Bake a default (= current package version) into the CANCAN_VERSION build-arg so the generated
        # compose is self-contained: plain `docker/podman compose up` interpolates without any extra env.
        self._apply_cancan_version_default(merged)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            yaml.safe_dump(merged, fp, sort_keys=False)
        return output_path

    def _apply_cancan_version_default(self, merged: Dict[str, Any]) -> None:
        """把 CANCAN_VERSION 构建参数改成带默认值的插值形式 ``${CANCAN_VERSION:-<pkg version>}``。
        Rewrite the CANCAN_VERSION build-arg to ``${CANCAN_VERSION:-<pkg version>}`` (with a default).

        默认值取当前安装的 cancan 包版本，因此即使调用方没设 CANCAN_VERSION 环境变量、
        直接用 docker/podman compose 起栈也能插值成功；显式设置时仍可覆盖。
        The default is the installed cancan version, so plain compose up works without the env var,
        while an explicit CANCAN_VERSION still overrides it.
        """
        from cancan_microstack.__version__ import __version__ as cancan_version

        default_expr = f"${{CANCAN_VERSION:-{cancan_version}}}"

        def _patch_args(container: Any) -> None:
            if isinstance(container, dict):
                args = container.get("args")
                if isinstance(args, dict) and "CANCAN_VERSION" in args:
                    args["CANCAN_VERSION"] = default_expr

        # 顶层 build 锚点（x-python-service-build 等）/ top-level build anchors
        for key, value in merged.items():
            if isinstance(key, str) and key.startswith("x-"):
                _patch_args(value)
        # 各服务的 build 段 / per-service build sections
        services = merged.get("services")
        if isinstance(services, dict):
            for svc_cfg in services.values():
                if isinstance(svc_cfg, dict):
                    _patch_args(svc_cfg.get("build"))

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
        if not isinstance(data, dict):  # pragma: no cover - defensive
            raise ValueError(f"Compose file must be a mapping: {path}")
        return data

    def _load_asset_yaml(self, logical_name: str) -> Dict[str, Any]:
        asset_path = self.asset_manager.resolve_path(logical_name)
        return self._load_yaml(asset_path)

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key not in result:
                result[key] = copy.deepcopy(value)
                continue
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def collect_override_paths(self, raw_values: Iterable[str]) -> Sequence[Path]:
        return [Path(item).expanduser().resolve() for item in raw_values]

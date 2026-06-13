"""Service runner utilities for controllersrv.

在启动服务前自动完成 workspace & overrides bootstrap，再按入口点动态加载。
Run bundled services after bootstrapping workspace/overrides and resolving entrypoints.
"""
import asyncio
import inspect
from importlib import import_module
from pathlib import Path
from typing import Dict

from cancan_microstack.runtime.overrides import bootstrap_from_workspace


class ServiceRunner:
    """加载并执行内置服务入口点 / Load and execute bundled service entrypoints."""

    _ENTRYPOINTS: Dict[str, str] = {
        "controllersrv": "cancan_microstack.cmd.controllersrv.run:main",
        "infrasrv": "cancan_microstack.cmd.infrasrv.run:main",
        "opsbffsrv": "cancan_microstack.cmd.opsbffsrv.run:main",
    }

    def run(
            self,
            service_name: str,
            *,
            host: str = "0.0.0.0",
            port: int = 8080,
            workspace: str | Path | None = None,
    ) -> None:
        asyncio.run(self.run_async(service_name, host=host, port=port, workspace=workspace))

    async def run_async(
            self,
            service_name: str,
            *,
            host: str = "0.0.0.0",
            port: int = 8080,
            workspace: str | Path | None = None,
    ) -> None:
        workspace_path = Path(workspace).expanduser().resolve() if workspace else None
        bootstrap_from_workspace(workspace_path)
        entry = self._ENTRYPOINTS.get(service_name)
        if not entry:
            raise ValueError(f"Unknown service '{service_name}'")
        module_name, func_name = entry.split(":")
        module = import_module(module_name)
        func = getattr(module, func_name)
        result = func(host=host, port=port)
        if inspect.isawaitable(result):
            await result
        elif callable(result):  # pragma: no cover - defensive
            maybe = result()
            if inspect.isawaitable(maybe):
                await maybe

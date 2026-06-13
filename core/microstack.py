"""High level orchestration helpers."""
from pathlib import Path
from typing import Sequence

from .assets import AssetManager
from .compose_builder import ComposeBuilder
from .runner import ServiceRunner


class CancanMicrostack:
    """Convenience facade bundling assets, compose builder, and service runner."""

    def __init__(self) -> None:
        self.assets = AssetManager()
        self.compose_builder = ComposeBuilder(self.assets)
        self.runner = ServiceRunner()

    def build_compose(
            self,
            *,
            workspace: Path,
            service_file: Path | None = None,
            overrides: Sequence[Path] | None = None,
            output: Path | None = None,
    ) -> Path:
        self._log(
            "Building Cancan compose file",
            workspace=workspace,
            service_file=service_file,
            overrides=overrides,
            output=output,
        )
        return self.compose_builder.build(
            workspace=workspace,
            service_file=service_file,
            overrides=overrides,
            output_file=output,
        )

    def export_asset(self, logical_name: str, destination: Path, overwrite: bool = False) -> Path:
        self._log("Exporting asset", logical_name=logical_name, destination=destination)
        return self.assets.export_asset(logical_name, destination, overwrite)

    def run_service(
            self,
            service_name: str,
            host: str = "0.0.0.0",
            port: int = 8080,
            workspace: Path | None = None,
    ) -> None:
        self._log(
            "Starting managed service",
            service=service_name,
            host=host,
            port=port,
            workspace=workspace,
        )
        self.runner.run(service_name, host=host, port=port, workspace=workspace)

    async def run_service_async(
            self,
            service_name: str,
            host: str = "0.0.0.0",
            port: int = 8080,
            workspace: Path | None = None,
    ) -> None:
        await self.runner.run_async(service_name, host=host, port=port, workspace=workspace)

    def _log(self, message: str, **fields) -> None:
        extras = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
        print(f"[cancan] {message} {extras}".strip())

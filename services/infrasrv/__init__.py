"""infrasrv namespace bootstrap (override aware)."""
from cancan_microstack.runtime.overrides import extend_service_package

__path__ = extend_service_package("infrasrv", __name__, __path__)  # type: ignore[name-defined]

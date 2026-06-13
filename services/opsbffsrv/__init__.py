"""opsbffsrv namespace bootstrap (override aware)."""
from cancan_microstack.runtime.overrides import extend_service_package

__path__ = extend_service_package("opsbffsrv", __name__, __path__)  # type: ignore[name-defined]

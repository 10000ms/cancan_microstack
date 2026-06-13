"""Command line interface helpers for Cancan Microstack."""
from datetime import datetime
from typing import Any


def log(message: str, **fields: Any) -> None:
    """Lightweight structured logger for CLI feedback."""

    prefix = datetime.now().isoformat(timespec="seconds")
    extras = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    print(f"[{prefix}] {message} {extras}".strip())


from .main import main  # noqa: E402  (import after helper definition)

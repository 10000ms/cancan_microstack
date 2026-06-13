"""Cancan Microstack – infrastructure microservice bundle and tooling."""
from .__version__ import (
    __author__,
    __author_email__,
    __description__,
    __license__,
    __title__,
    __url__,
    __version__,
)
from .core.assets import AssetManager, AssetRecord
from .core.compose_builder import ComposeBuilder
from .core.microstack import CancanMicrostack
from .core.runner import ServiceRunner

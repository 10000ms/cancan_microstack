"""Hooks package public API.

钩子模块公共入口 / Hook module public entry.

该包对外暴露全局 HookManager 的访问入口，避免调用方直接依赖具体实现文件。
Expose global HookManager accessors to avoid callers depending on internal modules.
"""

from .hook_registry import (
	get_hook_manager,
	reset_hook_manager,
)
from .pre_registration_hooks import HookManager

__all__ = [
	"HookManager",
	"get_hook_manager",
	"reset_hook_manager",
]

"""
钩子注册表 (Hook Registry)

提供全局唯一的 HookManager 实例和钩子注册功能。
这是整个 Hook 机制的入口点和管理中心。
"""

from typing import (
    Optional,
)
from .pre_registration_hooks import HookManager

# 全局唯一的 HookManager 实例变量。
# 使用 Optional 类型，并初始化为 None，以支持懒加载（lazy loading）。
_hook_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    """
    获取全局唯一的 HookManager 实例。

    采用单例模式（Singleton Pattern），确保在整个应用生命周期中，
    只有一个 HookManager 实例存在。
    如果实例不存在，则会创建一个新的实例。

    :return: 返回 HookManager 的全局实例。
    """
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager


def reset_hook_manager():
    """
    重置全局的 HookManager 实例。

    这个函数主要用于测试目的。在单元测试或集成测试中，
    可能需要在不同的测试用例之间隔离状态，
    通过重置 HookManager 可以确保每个测试用例都有一个干净的钩子环境。
    """
    global _hook_manager
    _hook_manager = None

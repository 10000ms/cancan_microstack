"""
钩子初始化模块
负责在服务启动时注册所有预定义的钩子
"""
from .builtin_hooks import register_all_hooks

from linglong_web.utils import logger


def initialize_hooks():
    """初始化所有钩子"""
    try:
        register_all_hooks()
        logger.info("Hooks initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize hooks: {e}")
        raise

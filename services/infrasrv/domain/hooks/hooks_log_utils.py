"""
Hooks 日志工具函数

提供与钩子相关的日志格式化功能，用于在 hooks 领域层中处理日志输出。
"""
from typing import (
    Optional,
    Dict,
    Any,
)
import logging
from datetime import (
    datetime,
    timezone,
)

from cancan_microstack.public.schemas.infra.hook_log import (
    HookLogData,
    HookInfo,
)
from cancan_microstack.public.const.hook_enums import HookLogAction, SensitiveFieldKey


def _sanitize_context(context_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    清洗上下文数据，移除敏感信息和限制字段长度
    Sanitize context data, remove sensitive info and limit field length
    
    Args:
        context_data: 原始上下文数据 / Original context data
        
    Returns:
        清洗后的上下文数据 / Sanitized context data
    """
    if not context_data:
        return None

    sanitized_context = {}
    for key, value in context_data.items():
        # 检查是否为敏感字段 / Check if sensitive field
        if key.lower() in [field.value for field in SensitiveFieldKey]:
            sanitized_context[key] = "***REDACTED***"
        else:
            # 限制值的长度，防止日志过大 / Limit value length to prevent large logs
            if isinstance(value, str) and len(value) > 100:
                sanitized_context[key] = value[:97] + "..."
            else:
                sanitized_context[key] = value

    return sanitized_context


def create_hook_log_data(
        hook_name: str,
        hook_type: str,
        message: str,
        priority: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        error: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None
) -> HookLogData:
    """
    创建钩子日志数据模型
    Create hook log data model
    
    Args:
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
        message: 日志消息 / Log message
        priority: 钩子优先级（可选）/ Hook priority (optional)
        context_data: 上下文数据（可选）/ Context data (optional)
        execution_time: 执行时间（可选）/ Execution time (optional)
        error: 错误信息（可选）/ Error message (optional)
        rejection_reason: 拒绝原因（可选）/ Rejection reason (optional)
        modifications: 修改内容（可选）/ Modifications (optional)
        
    Returns:
        HookLogData: 钩子日志数据模型实例 / Hook log data model instance
    """
    hook_info = HookInfo(name=hook_name, type=hook_type, priority=priority)

    return HookLogData(
        timestamp=datetime.now(timezone.utc).isoformat(),
        hook=hook_info,
        message=message,
        context=_sanitize_context(context_data),
        execution_time=execution_time,
        error=error,
        rejection_reason=rejection_reason,
        modifications=modifications
    )


def log_hook_registration(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str
) -> None:
    """
    记录钩子注册日志 / Log hook registration
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.REGISTERED
    )
    logger.info(log_data.model_dump_json(exclude_none=True))


def log_hook_deregistration(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str
) -> None:
    """
    记录钩子注销日志 / Log hook deregistration
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.DEREGISTERED
    )
    logger.info(log_data.model_dump_json(exclude_none=True))


def log_hook_execution_start(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str,
        metadata: Dict[str, Any]
) -> None:
    """
    记录钩子执行开始日志 / Log hook execution start
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
        metadata: 元数据 / Metadata
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.EXECUTION_STARTED,
        context_data=metadata
    )
    logger.info(log_data.model_dump_json(exclude_none=True))


def log_hook_execution_success(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str,
        execution_time: float,
        metadata: Dict[str, Any]
) -> None:
    """
    记录钩子执行成功日志 / Log hook execution success
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
        execution_time: 执行时间（秒）/ Execution time (seconds)
        metadata: 元数据 / Metadata
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.EXECUTION_SUCCESS,
        context_data=metadata,
        execution_time=execution_time
    )
    logger.info(log_data.model_dump_json(exclude_none=True))


def log_hook_execution_failure(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str,
        execution_time: float,
        error_msg: str,
        metadata: Dict[str, Any],
        exception: Optional[Exception] = None
) -> None:
    """
    记录钩子执行失败日志 / Log hook execution failure
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
        execution_time: 执行时间（秒）/ Execution time (seconds)
        error_msg: 错误信息 / Error message
        metadata: 元数据 / Metadata
        exception: 异常对象（可选）/ Exception object (optional)
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.EXECUTION_FAILURE,
        context_data=metadata,
        execution_time=execution_time,
        error=error_msg
    )
    if exception:
        logger.error(log_data.model_dump_json(exclude_none=True), exc_info=exception)
    else:
        logger.error(log_data.model_dump_json(exclude_none=True))


def log_hook_rejection(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str,
        reason: str,
        metadata: Dict[str, Any]
) -> None:
    """
    记录钩子拒绝服务注册日志 / Log hook rejection
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
        reason: 拒绝原因 / Rejection reason
        metadata: 元数据 / Metadata
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.REJECTION,
        context_data=metadata,
        rejection_reason=reason
    )
    logger.warning(log_data.model_dump_json(exclude_none=True))


def log_hook_service_modification(
        logger: logging.Logger,
        hook_name: str,
        hook_type: str,
        modifications: Dict[str, Any],
        metadata: Dict[str, Any]
) -> None:
    """
    记录钩子修改服务信息日志 / Log hook service modification
    
    Args:
        logger: 日志记录器实例 / Logger instance
        hook_name: 钩子名称 / Hook name
        hook_type: 钩子类型 / Hook type
        modifications: 修改的内容 / Modifications
        metadata: 元数据 / Metadata
    """
    log_data = create_hook_log_data(
        hook_name=hook_name,
        hook_type=hook_type,
        message=HookLogAction.MODIFICATION,
        context_data=metadata,
        modifications=modifications
    )
    logger.info(log_data.model_dump_json(exclude_none=True))

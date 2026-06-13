import logging
from typing import Optional

from linglong_web import LinglongConfigBase
from linglong_web import Rmanager

from cancan_microstack.runtime.workspace import ensure_server_log_dir
from cancan_microstack.public.logging.mq_handler import RabbitMQHandler

# 模块级变量，用于持有处理器实例
# Module-level variable to hold the handler instance
_handler: Optional[RabbitMQHandler] = None


async def setup_mq_logging(conf: LinglongConfigBase, service_name: str):
    """
    初始化并注册 RabbitMQ 日志处理器。
    此函数会将处理器添加到根日志记录器中，以便捕获所有日志。
    这是一个异步函数，应在应用资源（如 RabbitMQ 连接）准备就绪后调用。

    Initializes and registers the RabbitMQ log handler.
    This function adds the handler to the root logger to capture all logs.
    It is an async function and should be called after application resources
    (like the RabbitMQ connection) are ready.

    Args:
        conf: The application's configuration proxy object.
        service_name: The name of the service, used for routing log messages.
    """
    global _handler

    # 确保 server_log_data 目录存在，避免日志写入 venv 目录
    # Ensure the canonical server_log_data directory exists outside the venv
    ensure_server_log_dir()
    # 检查日志管道是否已启用
    # Check if the log pipeline is enabled in the configuration
    if not conf.LOG_PIPELINE_ENABLED:
        logging.info("MQ logging is disabled via LOG_PIPELINE_ENABLED config.")
        return

    # 确保 RabbitMQ 连接可用
    # Ensure the RabbitMQ connection is available
    if not Rmanager.mq_conn or Rmanager.mq_conn.is_closed:
        logging.error("Cannot setup MQ logging: RabbitMQ connection is not available in Rmanager.")
        return

    # 检查是否已存在处理器，避免重复添加
    # Check if a handler is already configured to prevent duplication
    root_logger = logging.getLogger()
    if any(isinstance(h, RabbitMQHandler) for h in root_logger.handlers):
        logging.warning("RabbitMQ log handler already configured.")
        return

    try:
        # 从配置中获取 exchange 名称
        # Get the exchange name from the configuration
        exchange_name = getattr(conf, "RABBITMQ_LOG_EXCHANGE", None) or conf.LOG_CONFIG.get(
            'exchange_name',
            'logs.topic.exchange',
        )
        routing_template = getattr(conf, "RABBITMQ_LOG_ROUTING_TEMPLATE", None) or "logs.business.{service}.{level}"

        # 创建处理器实例
        # Create the handler instance
        handler = RabbitMQHandler(
            connection=Rmanager.mq_conn,
            service_name=service_name,
            exchange_name=exchange_name,
            routing_template=routing_template,
        )

        # 异步初始化在 RabbitMQHandler 的 __init__ 中已经通过 run_coroutine_threadsafe 启动
        # aio_pika 的 RobustConnection 会自动处理重连，所以我们直接添加处理器即可
        # Async initialization is already started in RabbitMQHandler's __init__ via run_coroutine_threadsafe.
        # aio_pika's RobustConnection handles reconnections automatically, so we can add the handler directly.
        _handler = handler
        root_logger.addHandler(_handler)
        logging.info(f"RabbitMQ log handler added for service '{service_name}'. Initialization is in progress.")

    except Exception as e:
        logging.error(f"Failed to create and add RabbitMQ log handler: {e}", exc_info=True)
        _handler = None


async def shutdown_mq_logging():
    """
    异步关闭 RabbitMQ 日志处理器。
    这会从根日志记录器中移除处理器，并安全地关闭其 RabbitMQ 通道。

    Asynchronously shuts down the RabbitMQ log handler.
    This removes the handler from the root logger and safely closes its RabbitMQ channel.
    """
    global _handler
    if _handler:
        root_logger = logging.getLogger()
        logging.info("Shutting down RabbitMQ log handler.")
        try:
            # 首先从 logger 中移除处理器，停止接收新的日志
            # First, remove the handler from the logger to stop accepting new logs
            root_logger.removeHandler(_handler)

            # 调用处理器的异步关闭方法
            # Call the handler's asynchronous close method
            await _handler.close_async()
            logging.info("RabbitMQ log handler has been shut down.")
        except Exception as e:
            logging.error(f"Error during RabbitMQ log handler shutdown: {e}", exc_info=True)
        finally:
            _handler = None

"""
本模块提供了一个可重用的日志处理器，用于将日志记录发布到 RabbitMQ 交换机。
This module provides a reusable logging handler for publishing log records to a RabbitMQ exchange.
"""
import asyncio
import logging
import os
import socket
import threading
from concurrent.futures import Future
from datetime import (
    datetime,
    timezone,
)
from typing import (
    Any,
    Dict,
)

import aio_pika
import orjson
from aio_pika import (
    DeliveryMode,
    ExchangeType,
    Message,
    RobustConnection,
)
from nanoid import generate

from cancan_microstack.public.const.app_consts import LogLevelEnum
from cancan_microstack.public.schemas.logging.log_event import LogEventCreate
from linglong_web.utils import get_request_id
from linglong_web.utils import logger as app_logger


def build_log_routing_key(template: str, service_name: str, level: LogLevelEnum) -> str:
    """构建日志路由键 / Build log routing key."""
    try:
        return template.format(service=service_name, level=level.value.lower())
    except KeyError:
        return f"logs.business.{service_name}.{level.value.lower()}"


class RabbitMQHandler(logging.Handler):
    """
    一个将日志记录异步发布到 RabbitMQ 交换机 (Exchange) 的日志处理器。
    它的设计是线程安全的，旨在连接同步日志框架与异步 RabbitMQ 客户端 (`aio_pika`)。

    A logging handler that asynchronously publishes log records to a RabbitMQ exchange.
    It is designed to be thread-safe and to bridge the synchronous logging framework
    with an asynchronous RabbitMQ client (`aio_pika`).
    """

    def __init__(
            self,
            *,
            connection: RobustConnection,
            service_name: str,
            exchange_name: str,
            routing_template: str = "log.{service}.{level}",
            instance_id: str | None = None,
            loop: asyncio.AbstractEventLoop | None = None,
    ):
        """
        初始化处理器。
        Initializes the handler.

        Args:
            connection: 一个 aio_pika 的 RobustConnection 实例。/ An instance of aio_pika's RobustConnection.
            service_name: 当前服务的名称。/ Name of the current service.
            exchange_name: 要发布到的 RabbitMQ 交换机名称。/ Name of the RabbitMQ exchange to publish to.
            instance_id: 服务实例的唯一标识符。如果未提供，将自动生成。/ A unique identifier for the service instance. Auto-generated if not provided.
            loop: 运行 aio_pika 的事件循环。如果未提供，将获取当前正在运行的循环。/ The event loop running aio_pika. Gets the current running loop if not provided.
        """
        super().__init__()
        self._connection = connection
        self._service_name = service_name
        self._exchange_name = exchange_name
        self._routing_template = routing_template
        self._instance_id = instance_id or generate(size=12)
        self._loop = loop or asyncio.get_running_loop()

        self._channel: aio_pika.RobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

        self._host = os.environ.get("HOSTNAME") or socket.gethostname()
        self._cached_ip: str | None = None

        self._pending_futures: set[Future] = set()
        self._pending_lock = threading.Lock()

        # 在事件循环中初始化 Channel 和 Exchange
        # Initialize channel and exchange in the event loop
        asyncio.run_coroutine_threadsafe(self._initialize_mq_objects(), self._loop)

    async def _initialize_mq_objects(self):
        """
        创建 Channel 并声明 Exchange。此方法应在目标事件循环中运行。
        Create channel and declare exchange. This should be run in the target event loop.
        """
        try:
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name, ExchangeType.TOPIC, durable=True
            )
            app_logger.info(
                "RabbitMQHandler initialized for service '%s' on exchange '%s'",
                self._service_name,
                self._exchange_name,
            )
        except Exception as e:
            app_logger.error("Failed to initialize RabbitMQHandler: %s", e, exc_info=True)
            # 在这里可以更优雅地处理错误，例如设置一个失败状态
            # You might want to handle this more gracefully, e.g., by setting a failed state.

    def emit(self, record: logging.LogRecord) -> None:
        """
        格式化日志记录，并将其调度到事件循环上进行发布。
        这是从同步的 logging 调用到异步世界的桥梁。

        Formats the log record and schedules it for publishing on the event loop.
        This is the bridge from the synchronous logging call to the asynchronous world.
        """
        try:
            # 将日志级别字符串转换为枚举成员
            # Convert log level string to the enum member
            level = LogLevelEnum(record.levelname.upper())
        except (KeyError, ValueError):
            # 对自定义日志级别，默认使用 INFO
            # Default to INFO for custom log levels
            level = LogLevelEnum.INFO

        try:
            # 构建日志事件模型和路由键
            # Build the log event model and routing key
            event = self._build_log_event(record, level)
            routing_key = build_log_routing_key(self._routing_template, self._service_name, level)

            # 线程安全地在事件循环中调度发布任务
            # Thread-safely schedule the publish task in the event loop
            future = asyncio.run_coroutine_threadsafe(self._publish(event, routing_key), self._loop)

            # 追踪待处理的 future，以便在关闭时可以等待它们
            # Track the pending future so we can wait for it on close
            with self._pending_lock:
                self._pending_futures.add(future)
            future.add_done_callback(self._on_future_done)

        except Exception:
            self.handleError(record)

    def _on_future_done(self, future: Future) -> None:
        """
        当一个 future 完成时的回调，将其从待处理集合中移除。
        Callback for when a future is done to remove it from the pending set.
        """
        with self._pending_lock:
            self._pending_futures.discard(future)
        try:
            # 调用 result() 可以触发并记录在协程中发生的任何异常
            # Calling result() can trigger and log any exceptions that occurred in the coroutine
            future.result()
        except Exception as e:
            # 这是 `_publish` 协程中的异常浮现的地方
            # This is where exceptions from the `_publish` coroutine will be surfaced.
            app_logger.warning("Failed to publish log to RabbitMQ: %s", e)

    async def _publish(self, event: LogEventCreate, routing_key: str) -> None:
        """
        实际执行消息发布的协程。
        The actual coroutine that publishes the message.
        """
        if not self._exchange:
            # 如果初始化失败或仍在进行中，exchange 可能不可用
            # This can happen if initialization failed or is still in progress.
            app_logger.warning("RabbitMQ exchange not available, dropping log message.")
            return

        # 序列化并创建 aio_pika 消息对象
        # Serialize and create an aio_pika message object
        body = orjson.dumps(event.model_dump(mode="json"))
        message = Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        # 发布消息
        # Publish the message
        await self._exchange.publish(message, routing_key=routing_key, mandatory=False)

    def _build_log_event(self, record: logging.LogRecord, level: LogLevelEnum) -> LogEventCreate:
        """
        从 logging.LogRecord 构建一个 LogEventCreate Pydantic 模型。
        Constructs a LogEventCreate Pydantic model from a LogRecord.
        """
        return LogEventCreate(
            event_id=generate(size=16),
            service_name=self._service_name,
            instance_id=self._instance_id,
            level=level,
            message=record.getMessage(),
            timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
            ip=self._resolve_ip(),
            host=self._host,
            logger_name=record.name,
            file=record.pathname,
            line_no=record.lineno,
            func_name=record.funcName,
            trace_id=get_request_id(),
            metadata=self._collect_metadata(record),
        )

    def _collect_metadata(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        从日志记录中收集并字符串化元数据。
        Collects and stringifies metadata from the log record.
        """
        metadata: Dict[str, Any] = {
            "module": record.module,
            "process": record.process,
            "thread": record.thread,
        }
        # 添加传递给 logger 的任何额外字段，确保它们是可序列化的
        # Add any extra fields passed to the logger, ensuring they are serializable.
        standard_keys = {"args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
                         "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
                         "pathname", "process", "processName", "relativeCreated", "stack_info", "thread",
                         "threadName"}
        for key, value in record.__dict__.items():
            if key not in standard_keys:
                metadata[key] = str(value)  # 为安全起见，进行简单的字符串转换
        return metadata

    def _resolve_ip(self) -> str:
        """
        解析主机的非环回 IP 地址。
        Resolves the primary non-loopback IP address of the host.
        """
        if self._cached_ip:
            return self._cached_ip
        try:
            # 连接到一个公共 DNS 服务器以找到主出站 IP
            # Connect to a public DNS server to find the primary outbound IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1)
                s.connect(("8.8.8.8", 80))
                ip_addr = s.getsockname()[0]
        except Exception:
            ip_addr = "127.0.0.1"
        self._cached_ip = ip_addr
        return ip_addr

    async def close_async(self) -> None:
        """
        优雅地关闭 Channel。
        Gracefully close the channel.
        """
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
            app_logger.info("RabbitMQ channel closed.")

    def close(self) -> None:
        """
        关闭处理器，并等待任何待处理的日志消息被发送。
        Closes the handler, waiting for any pending log messages to be sent.
        """
        # 等待待处理的 futures 完成
        # Wait for pending futures to complete
        pending = list(self._pending_futures)
        if pending:
            # 这是一个同步上下文，所以我们不能 await
            # 我们在这里能做的就是记录下我们正在放弃待处理的消息
            # This is a synchronous context, so we can't await.
            # We can't do much here other than log that we are abandoning pending messages.
            app_logger.info("Closing RabbitMQHandler with %d pending messages.", len(pending))

        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.close_async(), self._loop)
        super().close()

"""
本模块为 infrasrv 提供日志消费服务。
This module provides the log ingestion service for infrasrv.
"""
import asyncio
from typing import Optional

import orjson
from aio_pika import (
    ExchangeType,
    RobustChannel,
    RobustQueue,
)
from aio_pika.abc import AbstractIncomingMessage
from aio_pika.robust_connection import RobustConnection

from cancan_microstack.public.schemas.logging.log_event import (
    LogEventCreate,
    LogEventDocument,
)
from linglong_web import LinglongConfig
from linglong_web import Rmanager
from linglong_web.utils import logger

from cancan_microstack.services.infrasrv.infrastructure.mongo.log_repository import InfraLogRepository


class LogIngestionService:
    """
    消费 RabbitMQ 中的日志消息，并将其持久化到 MongoDB。
    这是一个核心服务，负责将分布式系统中的日志集中存储。

    Consumes log messages from RabbitMQ and persists them into MongoDB.
    This is a core service responsible for centralizing logs from a distributed system.
    """

    def __init__(self) -> None:
        """初始化服务实例的内部状态。/ Initializes the internal state of the service instance."""
        self._repository: Optional[InfraLogRepository] = None
        self._connection: Optional[RobustConnection] = None
        self._channel: Optional[RobustChannel] = None
        self._queue: Optional[RobustQueue] = None
        self._consumer_tag: Optional[str] = None
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """
        启动日志消费服务。
        此方法是幂等的，如果服务已启动则不会执行任何操作。
        它会根据配置决定是否启用消费者，并初始化数据库和 RabbitMQ 连接。

        Starts the log ingestion service.
        This method is idempotent and does nothing if the service is already started.
        It checks the configuration to decide whether to enable the consumer,
        then initializes the database and RabbitMQ connections.
        """
        if self._started:
            return
        if not LinglongConfig.LOG_PIPELINE_CONSUMER_ENABLED:
            logger.info("Log pipeline consumer disabled via config")
            return

        async with self._lock:
            if self._started:
                return
            self._repository = InfraLogRepository()
            await self._connect_rabbitmq()
            self._started = True
            logger.info("Log ingestion service started")

    async def _connect_rabbitmq(self) -> None:
        """
        使用全局 RabbitMQ 连接建立 Channel、Exchange 和 Queue，并开始消费。
        Establishes a channel, exchange, and queue using the global RabbitMQ connection, and starts consuming.
        """
        if not Rmanager.mq_conn or Rmanager.mq_conn.is_closed:
            logger.error("RabbitMQ connection is not available. Cannot start log ingestion.")
            raise RuntimeError("RabbitMQ connection not initialized")

        self._connection = Rmanager.mq_conn
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=int(LinglongConfig.RABBITMQ_LOG_PREFETCH))

        exchange = await self._channel.declare_exchange(
            LinglongConfig.RABBITMQ_LOG_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        self._queue = await self._channel.declare_queue(
            LinglongConfig.RABBITMQ_LOG_QUEUE,
            durable=True,
        )
        await self._queue.bind(exchange, routing_key=LinglongConfig.RABBITMQ_LOG_BINDING_KEY)
        self._consumer_tag = await self._queue.consume(self._handle_message)
        logger.info("RabbitMQ consumer setup complete.")

    async def _handle_message(self, message: AbstractIncomingMessage) -> None:
        """
        处理接收到的 RabbitMQ 消息的回调函数。
        它负责解析消息、转换数据模型并将其插入数据库。

        Callback function to process incoming RabbitMQ messages.
        It is responsible for parsing the message, transforming the data model, and inserting it into the database.
        """
        if not self._repository:
            await message.ack()
            return

        # requeue=True：当处理（尤其是 Mongo 写入）失败并抛出异常时，nack 并重新入队，
        # 避免静默丢日志；正常退出才会 ACK。
        # requeue=True: when processing (notably the Mongo write) fails and raises, nack and
        # requeue the message instead of silently dropping the log; ACK only on clean exit.
        async with message.process(requeue=True):
            try:
                payload = orjson.loads(message.body)
                event = LogEventCreate.model_validate(payload)
                document = LogEventDocument(**event.model_dump())
                document.metadata_flattened = self._flatten_metadata(document.metadata)

                await self._repository.insert_event(document)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to process log message: %s", exc, exc_info=True)
                # 重新抛出，让 message.process(requeue=True) 执行 nack(requeue=True)，避免丢日志
                # Re-raise so message.process(requeue=True) performs nack(requeue=True), preventing log loss
                raise

    @staticmethod
    def _flatten_metadata(metadata: dict[str, object]) -> list[str]:
        """
        将元数据字典扁平化为字符串列表，以便于进行文本搜索。
        Flattens the metadata dictionary into a list of strings for easier text searching.
        """
        tokens: list[str] = []
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                tokens.append(f"{key}:{value}")
            else:
                tokens.append(f"{key}:{value!r}")
        return tokens

    async def shutdown(self) -> None:
        """
        停止日志消费并释放所有资源（如 RabbitMQ Channel 和数据库连接）。
        Stops log ingestion and releases all resources, such as the RabbitMQ channel and database connection.
        """
        async with self._lock:
            if not self._started:
                return
            if self._queue and self._consumer_tag:
                await self._queue.cancel(self._consumer_tag)
            if self._channel and not self._channel.is_closed:
                await self._channel.close()
            self._queue = None
            self._channel = None
            self._connection = None
            self._repository = None
            self._consumer_tag = None
            self._started = False
            logger.info("Log ingestion service stopped")

    def get_repository(self) -> Optional[InfraLogRepository]:
        """
        获取数据库仓库实例，用于其他可能的交互。
        Returns the database repository instance for other potential interactions.
        """
        return self._repository


_log_ingestion_service: Optional[LogIngestionService] = None


def get_log_ingestion_service() -> LogIngestionService:
    """
    通过单例模式获取日志消费服务实例。
    Returns the singleton log ingestion service instance.
    """
    global _log_ingestion_service
    if _log_ingestion_service is None:
        _log_ingestion_service = LogIngestionService()
    return _log_ingestion_service

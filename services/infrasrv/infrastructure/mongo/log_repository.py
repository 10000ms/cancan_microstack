"""MongoDB 日志存储仓库 / MongoDB repository for log documents."""
import asyncio
from datetime import datetime
from typing import (
    Any,
    List,
)

from pymongo.asynchronous.collection import AsyncCollection
from pymongo import ASCENDING, DESCENDING

from cancan_microstack.public.schemas.logging.log_event import LogEventDocument
from linglong_web import LinglongConfig
from linglong_web import Rmanager
from linglong_web.utils import logger


class InfraLogRepository:
    """封装 MongoDB 访问逻辑 / Encapsulate MongoDB operations for logs."""

    def __init__(self) -> None:
        """
        初始化仓库。
        它从全局资源管理器获取 MongoDB 客户端，并从配置中获取数据库和集合名称。
        
        Initializes the repository.
        It reads database/collection names from the config; the MongoDB client is read
        lazily at use time (see _init_collection), since resource initialization may happen
        later in the server lifecycle.
        """
        # 注意：不要在 __init__ 缓存 Rmanager.MongoClient。
        # 该仓库可能在资源初始化之前被创建，缓存 None 会导致整个进程拿不到 client。
        # 与 opsbffsrv 的 LogQueryRepository 保持一致：在使用处惰性读取。
        # Note: do NOT cache Rmanager.MongoClient at __init__ time. This repo may be created
        # before resources are initialized; caching None would make the client unavailable forever.
        # Aligned with opsbffsrv's LogQueryRepository: read it lazily at use time.
        self._db_name = LinglongConfig.MONGODB_DB
        self._collection_name = LinglongConfig.MONGODB_COLLECTION
        self._collection: AsyncCollection | None = None
        self._index_lock = asyncio.Lock()

    async def _init_collection(self) -> AsyncCollection:
        """
        按需初始化集合对象并确保索引存在。
        使用锁来防止并发的索引创建。

        Initializes the collection object on-demand and ensures indexes exist.
        Uses a lock to prevent concurrent index creation.
        """
        if self._collection is not None:
            return self._collection

        async with self._index_lock:
            # Double-check after acquiring the lock
            if self._collection is not None:
                return self._collection

            client = Rmanager.MongoClient
            if not client:
                raise RuntimeError("MongoDB client is not available in Rmanager.")

            collection = client[self._db_name][self._collection_name]
            await self._ensure_indexes(collection)
            self._collection = collection
            logger.info(
                "InfraLogRepository collection '%s/%s' initialized.", self._db_name, self._collection_name
            )
            return self._collection

    async def _get_collection(self) -> AsyncCollection:
        """获取集合对象，如果需要则先进行初始化。/ Gets the collection object, initializing it if necessary."""
        if self._collection is not None:
            return self._collection
        return await self._init_collection()

    async def _ensure_indexes(self, collection: AsyncCollection) -> None:
        """确保 MongoDB 集合上存在所有必需的索引。/ Ensures all required indexes exist on the MongoDB collection."""
        await collection.create_index(
            [("service_name", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_service_ts",
        )
        await collection.create_index(
            [("level", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_level_ts",
        )
        await collection.create_index(
            [("ip", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_ip_ts",
        )
        await collection.create_index(
            [("func_name", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_func_ts",
        )
        await collection.create_index(
            [("message", "text"), ("metadata_flattened", "text")],
            name="idx_text_search",
            default_language="english",
        )

    async def insert_event(self, document: LogEventDocument) -> None:
        """向集合中插入一个新的日志文档。/ Inserts a new log document into the collection."""
        collection = await self._get_collection()
        payload = document.model_dump()
        await collection.insert_one(payload)

    async def cleanup_older_than(self, cutoff: datetime, batch_limit: int) -> int:
        """删除早于给定截止时间的日志。/ Deletes logs older than a given cutoff time."""
        collection = await self._get_collection()
        cursor = (
            collection.find({"timestamp": {"$lt": cutoff}}, projection={"_id": 1})
            .sort("timestamp", ASCENDING)
            .limit(batch_limit)
        )
        ids: List[Any] = [doc["_id"] async for doc in cursor]

        if not ids:
            return 0
        result = await collection.delete_many({"_id": {"$in": ids}})
        return int(result.deleted_count)

    async def count_by_time_range(self, start: datetime, end: datetime) -> int:
        """计算给定时间范围内的文档数量。/ Counts documents within a given time range."""
        collection = await self._get_collection()
        return await collection.count_documents({"timestamp": {"$gte": start, "$lte": end}})

    @property
    async def collection(self) -> AsyncCollection:
        """提供对底层集合对象的异步属性访问。/ Provides async property access to the underlying collection object."""
        return await self._get_collection()

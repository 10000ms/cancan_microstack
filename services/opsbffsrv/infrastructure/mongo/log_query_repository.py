"""MongoDB 日志查询仓库 / Mongo-backed log query repository."""
import asyncio
from typing import (
    Any,
    Dict,
    List,
    Tuple,
)

from pymongo.asynchronous.collection import AsyncCollection
from pymongo import DESCENDING

from cancan_microstack.public.schemas.logging.log_event import LogEventDocument
from linglong_web import LinglongConfig
from linglong_web import Rmanager
from linglong_web.utils import logger


class LogQueryRepository:
    """封装日志查询操作 / Encapsulate log query operations."""

    def __init__(self) -> None:
        """
        Initializes the repository using the global MongoDB client.
        """
        # 注意：不能在 __init__ 时缓存 Rmanager.MongoClient。
        # Note: Do NOT cache Rmanager.MongoClient at __init__ time.
        #
        # 说明 / Rationale:
        # - 该 Repository 可能在模块 import 阶段被创建（全局单例）。
        #   It may be instantiated at import time (module-level singleton).
        # - 资源初始化（init_resources）发生在服务启动生命周期更靠后的位置。
        #   Resource initialization happens later in the server lifecycle.
        # - 如果这里缓存了 None，会导致整个进程里一直拿不到 Mongo client。
        #   Caching None here makes Mongo client unavailable forever.
        self._collection: AsyncCollection | None = None
        self._init_lock = asyncio.Lock()

    async def _get_collection(self) -> AsyncCollection:
        """Lazily initializes and returns the MongoDB collection object."""
        if self._collection is not None:
            return self._collection

        async with self._init_lock:
            if self._collection is not None:
                return self._collection

            client = Rmanager.MongoClient
            if not client:
                raise RuntimeError("MongoDB client is not available in Rmanager.")

            db_name = LinglongConfig.MONGODB_DB
            collection_name = LinglongConfig.MONGODB_COLLECTION
            if not db_name or not collection_name:
                raise RuntimeError(
                    "MongoDB config is not available: MONGODB_DB/MONGODB_COLLECTION is empty."
                )

            collection = client[db_name][collection_name]
            self._collection = collection
            logger.info(
                "LogQueryRepository collection '%s/%s' initialized.", db_name, collection_name
            )
            return self._collection

    async def query_logs(
            self,
            filters: Dict[str, Any],
            skip: int,
            limit: int,
    ) -> Tuple[List[LogEventDocument], int]:
        collection = await self._get_collection()
        cursor = (
            collection.find(filters)
            .sort("timestamp", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        raw_docs = await cursor.to_list(length=limit)
        events = [self._convert_document(doc) for doc in raw_docs]
        total = await collection.count_documents(filters)
        return events, int(total)

    def _convert_document(self, doc: Dict[str, Any]) -> LogEventDocument:
        doc = dict(doc)
        doc.pop("_id", None)
        return LogEventDocument.model_validate(doc)

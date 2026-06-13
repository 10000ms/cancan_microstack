"""日志查询领域服务 / Log query domain service."""
import re
from datetime import timedelta
from typing import (
    Any,
    Dict,
    List,
)

from cancan_microstack.public.schemas.logging.log_event import (
    LogQueryRequest,
    LogQueryResponse,
)
from linglong_web.utils import logger

from cancan_microstack.services.opsbffsrv.infrastructure.mongo.log_query_repository import LogQueryRepository


class LogQueryDomain:
    """实现日志查询业务规则 / Implements log query business rules."""

    def __init__(self, repository: LogQueryRepository) -> None:
        self._repository = repository

    async def search_logs(self, request: LogQueryRequest, max_range_days: int) -> LogQueryResponse:
        self._validate_range(request, max_range_days)
        filters = self._build_filters(request)
        skip = (request.page - 1) * request.page_size
        events, total = await self._repository.query_logs(filters, skip, request.page_size)
        has_next = (skip + len(events)) < total
        logger.debug(
            "Log query completed: filters=%s total=%s page=%s page_size=%s", filters, total, request.page,
            request.page_size
        )
        return LogQueryResponse(
            items=events,
            total=total,
            page=request.page,
            page_size=request.page_size,
            has_next=has_next,
        )

    def _validate_range(self, request: LogQueryRequest, max_range_days: int) -> None:
        max_delta = timedelta(days=max_range_days)
        actual_range = request.end_time - request.start_time
        if actual_range > max_delta:
            raise ValueError(f"Time range exceeds {max_range_days} days")

    @staticmethod
    def _clean_values(values: List[str] | None) -> List[str]:
        """清理输入字符串列表，移除空值并去重
        Clean string list inputs by trimming, dropping empty items, and de-duplicating
        """
        if not values:
            return []

        result: List[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if not normalized:
                continue
            if normalized not in result:
                result.append(normalized)
        return result

    def _build_filters(self, request: LogQueryRequest) -> Dict[str, Any]:
        cleaned_service_names = self._clean_values(request.service_names)
        cleaned_levels = [level.value for level in request.levels] if request.levels else []
        cleaned_method_names = self._clean_values(request.method_names)
        cleaned_ip_addresses = self._clean_values(request.ip_addresses)
        cleaned_instance_ids = self._clean_values(request.instance_ids)
        cleaned_keywords = self._clean_values(request.keywords)

        filters: Dict[str, Any] = {
            "service_name": {"$in": cleaned_service_names},
            "timestamp": {"$gte": request.start_time, "$lte": request.end_time},
        }
        if cleaned_levels:
            filters["level"] = {"$in": cleaned_levels}
        if cleaned_method_names:
            filters["func_name"] = {"$in": cleaned_method_names}
        if cleaned_ip_addresses:
            filters["ip"] = {"$in": cleaned_ip_addresses}
        if cleaned_instance_ids:
            filters["instance_id"] = {"$in": cleaned_instance_ids}
        if cleaned_keywords:
            # 同时搜索 message/trace/event 以及 metadata 中常见 reqid 字段
            # Search message/trace/event and common reqid fields in metadata
            keyword_pattern = "|".join(re.escape(keyword) for keyword in cleaned_keywords)
            filters["$or"] = [
                {"message": {"$regex": keyword_pattern, "$options": "i"}},
                {"trace_id": {"$regex": keyword_pattern, "$options": "i"}},
                {"event_id": {"$regex": keyword_pattern, "$options": "i"}},
                {"metadata_flattened": {"$regex": keyword_pattern, "$options": "i"}},
                {"metadata.oid": {"$regex": keyword_pattern, "$options": "i"}},
                {"metadata.reqid": {"$regex": keyword_pattern, "$options": "i"}},
                {"metadata.trace_id": {"$regex": keyword_pattern, "$options": "i"}},
            ]
        return filters

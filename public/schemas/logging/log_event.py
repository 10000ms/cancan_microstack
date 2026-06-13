"""业务日志事件模型 / Business log event models."""
from datetime import (
    datetime,
    timezone,
)
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
)

from cancan_microstack.public.const.app_consts import LogLevelEnum


class LogEventBase(BaseModel):
    """日志事件公共字段 / Shared log event fields."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    event_id: str = Field(..., description="日志事件唯一 ID / Unique log event id")
    service_name: str = Field(..., description="服务名称 / Service name")
    instance_id: str = Field(..., description="实例 ID / Instance identifier")
    level: LogLevelEnum = Field(..., description="日志等级 / Log level")
    message: str = Field(..., description="日志内容 / Log message body")
    timestamp: datetime = Field(..., description="UTC 时间戳 / UTC timestamp")
    ip: str = Field(..., description="实例 IP / Instance IP address")
    host: str = Field(..., description="主机名 / Hostname")
    logger_name: str = Field(..., description="记录器名称 / Logger name")
    file: str = Field(..., description="源文件路径 / Source file path")
    line_no: int = Field(..., description="行号 / Source line number")
    func_name: str = Field(..., description="函数名 / Function name")
    trace_id: str = Field(..., description="请求/链路 ID / Trace identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据 / Additional metadata")

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        """确保输出为带时区的 ISO 8601 字符串。
        Ensure JSON output is timezone-aware ISO 8601.
        """

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class LogEventCreate(LogEventBase):
    """生产端使用的日志事件结构 / Producer-side log event structure."""


class LogEventDocument(LogEventBase):
    """MongoDB 持久化结构 / MongoDB document representation."""

    metadata_flattened: List[str] = Field(
        default_factory=list,
        description="扁平化元数据用于搜索 / Flattened metadata tokens",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="文档创建时间 / Document creation time",
    )

    @field_serializer("created_at", when_used="json")
    def serialize_created_at(self, value: datetime) -> str:
        """确保输出为带时区的 ISO 8601 字符串。
        Ensure JSON output is timezone-aware ISO 8601.
        """

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class LogQueryRequest(BaseModel):
    """日志查询请求参数 / Log query request DTO."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    service_names: List[str] = Field(..., min_length=1, description="服务列表 / Service names")
    start_time: datetime = Field(..., description="开始时间 / Start time (UTC)")
    end_time: datetime = Field(..., description="结束时间 / End time (UTC)")
    levels: Optional[List[LogLevelEnum]] = Field(default=None, description="日志等级过滤 / Optional log levels")
    keywords: Optional[List[str]] = Field(default=None, description="关键字列表 / Keywords for text search")
    method_names: Optional[List[str]] = Field(default=None, description="方法名过滤 / Method name filters")
    ip_addresses: Optional[List[str]] = Field(default=None, description="IP 过滤 / IP filters")
    instance_ids: Optional[List[str]] = Field(default=None, description="实例过滤 / Instance filters")
    page: int = Field(default=1, ge=1, description="页码 / Page number")
    page_size: int = Field(default=100, ge=1, le=500, description="每页数量 / Page size")

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, end_time: datetime, info: ValidationInfo) -> datetime:
        """确保结束时间大于开始时间 / Ensure end_time > start_time."""
        start_time = info.data.get("start_time")
        if start_time and end_time <= start_time:
            raise ValueError("end_time must be greater than start_time")
        return end_time


class LogQueryResponse(BaseModel):
    """日志查询响应结构 / Log query response DTO."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    items: List[LogEventDocument] = Field(default_factory=list, description="日志列表 / Log entries")
    total: int = Field(default=0, ge=0, description="总数 / Total count")
    page: int = Field(default=1, ge=1, description="当前页 / Current page")
    page_size: int = Field(default=100, ge=1, description="每页数量 / Page size")
    has_next: bool = Field(default=False, description="是否有下一页 / Whether more pages exist")

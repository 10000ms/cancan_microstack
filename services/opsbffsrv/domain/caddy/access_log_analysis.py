"""
Caddy 访问日志分析领域服务
包含访问日志查询和分析的核心业务逻辑
"""
from typing import (
    List,
    Optional,
    Dict,
    Any,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from cancan_microstack.public.const.caddy_consts import SecurityEventType
from cancan_microstack.public.schemas.caddy import CaddyAccessLog, AccessLogQuery
from cancan_microstack.public.schemas.caddy.analysis import SuspiciousIP, ErrorPatternAnalysis
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_access_log import (
    get_access_log_by_id,
    get_access_log_by_request_id,
    query_access_logs,
    get_logs_by_ip,
    get_logs_by_service,
    get_waf_blocked_logs,
    get_rate_limited_logs,
    get_country_distribution,
    get_status_code_distribution,
    create_access_log,
    batch_create_access_logs,
    delete_old_logs,
    count_access_logs,
)
from cancan_microstack.services.opsbffsrv.infrastructure.caddy.access_log_parser import access_log_parser
from linglong_web.utils import logger


class AccessLogAnalysisDomain:
    """访问日志分析领域服务"""

    async def ingest_log_entry(self, log_data: Dict[str, Any]) -> CaddyAccessLog:
        """
        接收并处理单条访问日志
        
        业务流程：
        1. 解析日志数据
        2. 提取 IP 地理位置信息
        3. 存储到数据库
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            访问日志对象
        """
        logger.debug("Ingesting access log entry")

        # 解析日志数据
        log_entry = access_log_parser.parse_dict_log(log_data)
        if not log_entry:
            raise ValueError("Failed to parse access log data")

        # 存储到数据库
        db_log = await create_access_log(log_entry)
        logger.debug(f"Access log entry stored: {db_log.id}")

        return db_log

    async def ingest_log_batch(self, log_lines: List[str]) -> int:
        """
        批量接收并处理访问日志
        
        Args:
            log_lines: JSON 格式的日志行列表
            
        Returns:
            成功处理的日志数量
        """
        logger.info(f"Ingesting batch of {len(log_lines)} access log entries")

        # 解析所有日志行
        log_entries = []
        for line in log_lines:
            try:
                log_entry = access_log_parser.parse_json_log(line)
                if log_entry:
                    log_entries.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to parse log line: {e}")
                continue

        if not log_entries:
            logger.warning("No valid log entries to ingest")
            return 0

        # 批量存储到数据库
        await batch_create_access_logs(log_entries)
        logger.info(f"Successfully ingested {len(log_entries)} access log entries")

        return len(log_entries)

    async def search_logs(self, query: AccessLogQuery) -> List[CaddyAccessLog]:
        """
        搜索访问日志
        
        Args:
            query: 查询参数对象
            
        Returns:
            访问日志列表
        """
        logger.info(f"Searching access logs with filters: {query.model_dump()}")

        # 验证查询参数
        self._validate_query_params(query)

        return await query_access_logs(query)

    async def get_log_details(self, log_id: int) -> Optional[CaddyAccessLog]:
        """
        获取访问日志详情
        
        Args:
            log_id: 日志 ID
            
        Returns:
            访问日志对象或 None
        """
        return await get_access_log_by_id(log_id)

    async def get_log_by_request_id(self, request_id: str) -> Optional[CaddyAccessLog]:
        """
        根据请求 ID 获取访问日志
        
        Args:
            request_id: 请求 ID
            
        Returns:
            访问日志对象或 None
        """
        return await get_access_log_by_request_id(request_id)

    async def get_logs_for_ip(self, client_ip: str, limit: int = 100) -> List[CaddyAccessLog]:
        """
        获取指定 IP 的访问日志
        
        Args:
            client_ip: 客户端 IP
            limit: 返回数量限制
            
        Returns:
            访问日志列表
        """
        logger.info(f"Fetching logs for IP: {client_ip}")
        return await get_logs_by_ip(client_ip, limit)

    async def get_logs_for_service(self, service: str, limit: int = 100) -> List[CaddyAccessLog]:
        """
        获取指定服务的访问日志
        
        Args:
            service: 服务名称
            limit: 返回数量限制
            
        Returns:
            访问日志列表
        """
        logger.info(f"Fetching logs for service: {service}")
        return await get_logs_by_service(service, limit)

    async def get_security_events(self, event_type: SecurityEventType, limit: int = 100) -> List[CaddyAccessLog]:
        """
        获取安全事件日志
        
        Args:
            event_type: 事件类型
            limit: 返回数量限制
            
        Returns:
            访问日志列表
        """
        logger.info(f"Fetching security events: {event_type}")

        if event_type == SecurityEventType.WAF_BLOCKED:
            return await get_waf_blocked_logs(limit)
        if event_type == SecurityEventType.RATE_LIMITED:
            return await get_rate_limited_logs(limit)

        raise ValueError(f"Invalid event type: {event_type}")

    async def analyze_geographic_distribution(
            self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        分析访问的地理分布
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            国家分布列表
        """
        logger.info("Analyzing geographic distribution")
        return await get_country_distribution(start_time, end_time)

    async def analyze_status_code_distribution(
            self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        分析 HTTP 状态码分布
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            状态码分布列表
        """
        logger.info("Analyzing status code distribution")
        return await get_status_code_distribution(start_time, end_time)

    async def detect_suspicious_ips(
            self, time_window: int = 60, request_threshold: int = 1000
    ) -> List[SuspiciousIP]:
        """
        检测可疑 IP（高频访问）
        
        业务规则：在指定时间窗口内，请求数超过阈值的 IP 被标记为可疑
        
        Args:
            time_window: 时间窗口（分钟）
            request_threshold: 请求数阈值
            
        Returns:
            可疑 IP 列表
        """
        logger.info(f"Detecting suspicious IPs (window={time_window}min, threshold={request_threshold})")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=time_window)

        # 查询指定时间窗口内的所有日志
        query = AccessLogQuery(start_time=start_time, end_time=end_time, limit=10000, offset=0)
        logs = await query_access_logs(query)

        # 统计每个 IP 的请求数
        ip_counts: Dict[str, int] = {}
        for log in logs:
            ip_counts[log.client_ip] = ip_counts.get(log.client_ip, 0) + 1

        # 筛选超过阈值的 IP
        suspicious_ips = [
            SuspiciousIP(ip=ip, count=count)
            for ip, count in ip_counts.items()
            if count > request_threshold
        ]

        # 按请求数降序排序
        suspicious_ips.sort(key=lambda x: x.count, reverse=True)

        logger.info(f"Found {len(suspicious_ips)} suspicious IPs")
        return suspicious_ips

    async def analyze_error_patterns(self, hours: int = 24) -> ErrorPatternAnalysis:
        """
        分析错误模式
        
        Args:
            hours: 过去多少小时
            
        Returns:
            错误分析结果
        """
        logger.info(f"Analyzing error patterns for the past {hours} hours")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # 查询错误日志（4xx 和 5xx）
        query = AccessLogQuery(start_time=start_time, end_time=end_time, limit=5000, offset=0)
        all_logs = await query_access_logs(query)

        # 筛选错误日志
        error_logs = [log for log in all_logs if log.status_code >= 400]

        # 按路径统计错误
        error_by_path: Dict[str, int] = {}
        for log in error_logs:
            error_by_path[log.path] = error_by_path.get(log.path, 0) + 1

        # 按状态码统计错误
        error_by_status: Dict[int, int] = {}
        for log in error_logs:
            error_by_status[log.status_code] = error_by_status.get(log.status_code, 0) + 1

        return ErrorPatternAnalysis(
            total_errors=len(error_logs),
            error_rate=len(error_logs) / len(all_logs) if all_logs else 0,
            top_error_paths=sorted(error_by_path.items(), key=lambda x: x[1], reverse=True)[:10],
            error_by_status=error_by_status,
        )

    async def cleanup_old_logs(self, days: int = 30) -> int:
        """
        清理旧的访问日志
        
        业务规则：保留最近 N 天的日志
        
        Args:
            days: 保留天数
            
        Returns:
            删除的记录数
        """
        logger.info(f"Cleaning up access logs older than {days} days")

        before_time = datetime.now(timezone.utc) - timedelta(days=days)
        deleted_count = await delete_old_logs(before_time)

        logger.info(f"Cleaned up {deleted_count} old access log records")
        return deleted_count

    async def get_log_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        获取日志数量
        
        Args:
            filters: 过滤条件
            
        Returns:
            日志数量
        """
        return await count_access_logs(filters)

    def _validate_query_params(self, query: AccessLogQuery):
        """
        验证查询参数
        
        Args:
            query: 查询参数对象
            
        Raises:
            ValueError: 参数无效
        """
        # 验证时间范围
        if query.start_time and query.end_time and query.start_time > query.end_time:
            raise ValueError("Start time must be before end time")

        # 验证 limit
        if query.limit > 1000:
            raise ValueError("Limit cannot exceed 1000")

        # 验证响应时间范围
        if query.min_response_time and query.max_response_time:
            if query.min_response_time > query.max_response_time:
                raise ValueError("Min response time must be less than max response time")

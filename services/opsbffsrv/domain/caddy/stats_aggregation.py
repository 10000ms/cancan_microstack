"""
Caddy 统计数据聚合领域服务
包含统计数据聚合和分析的核心业务逻辑
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from linglong_web.utils import logger

from cancan_microstack.public.const.caddy_consts import InternalRequestPath
from cancan_microstack.public.schemas.caddy.analysis import (
    RealtimeStatsMetadata,
    StatsAggregationPayload,
    TopCountryStatsMetadata,
    TopIPStatsMetadata,
)
from cancan_microstack.public.schemas.caddy import CaddyStats, StatsQuery
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_stats import (
    get_stats_by_id,
    query_stats,
    get_global_stats,
    get_service_stats,
    get_route_stats,
    get_country_stats,
    get_ip_stats,
    get_latest_stats,
    create_stats,
    upsert_stats,
    delete_old_stats,
    count_stats,
)
from cancan_microstack.services.opsbffsrv.infrastructure.db.operate.caddy_access_log import (
    query_access_logs,
    get_country_distribution,
    get_ip_distribution,
    get_status_code_distribution,
    get_timeseries_distribution,
)


class StatsAggregationDomain:
    """统计数据聚合领域服务"""

    @staticmethod
    def _is_system_internal_request(path: Optional[str]) -> bool:
        """判断是否为系统内部请求（需从统计中排除）
        Determine whether request path is internal system traffic to exclude
        """
        if not path:
            return False
        return (
            path == InternalRequestPath.HEALTH_CHECK
            or path.startswith(InternalRequestPath.INTERNAL_PREFIX)
            or path.startswith(InternalRequestPath.OPSBFF_API_PREFIX)
        )

    async def aggregate_stats_for_period(
            self,
            start_time: datetime,
            end_time: datetime,
            stat_period: str,
            dimension_type: str,
            dimension_value: Optional[str] = None
    ) -> CaddyStats:
        """
        为指定时间段聚合统计数据
        
        业务规则：
        1. 从访问日志中聚合原始数据
        2. 计算请求数、错误率、响应时间分位数等
        3. 使用 upsert 避免重复统计
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            stat_period: 统计周期（minute/hour/day/month）
            dimension_type: 维度类型（global/service/route/ip/country）
            dimension_value: 维度值
            
        Returns:
            聚合后的统计对象
        """
        logger.info(f"Aggregating stats for period: {stat_period}, dimension: {dimension_type}")

        # 验证统计周期
        self._validate_stat_period(stat_period)

        # 验证维度类型
        self._validate_dimension_type(dimension_type)

        # 从访问日志聚合数据
        aggregated_data = await self._aggregate_from_access_logs(
            start_time, end_time, dimension_type, dimension_value
        )

        # 构建统计对象
        stats = CaddyStats(
            stat_time=self._normalize_time_by_period(start_time, stat_period),
            stat_period=stat_period,
            dimension_type=dimension_type,
            dimension_value=dimension_value,
            **aggregated_data
        )

        # 使用 upsert 保存统计数据
        db_stats = await upsert_stats(stats)
        logger.info(f"Stats aggregated and saved: {db_stats.id}")

        return db_stats

    async def get_realtime_stats(self, dimension_type: str = 'global', dimension_value: Optional[str] = None) -> \
    Optional[CaddyStats]:
        """
        获取实时统计数据（最近一分钟）
        
        Args:
            dimension_type: 维度类型
            dimension_value: 维度值
            
        Returns:
            最新的统计对象或 None
        """
        logger.info(f"Fetching realtime stats for dimension: {dimension_type}")

        # 获取最近一分钟的统计数据
        end_time = datetime.now(timezone.utc)
        # 尝试从数据库获取已聚合的统计
        latest_stats = await get_latest_stats(dimension_type, dimension_value)

        # 新鲜且非 0 数据可直接使用，避免不必要重算
        # Fresh non-zero snapshot can be reused directly
        if latest_stats and (datetime.now(timezone.utc) - latest_stats.stat_time).total_seconds() <= 120 \
                and latest_stats.total_requests > 0:
            return latest_stats

        logger.info("Realtime stats missing/stale/zero, building fallback snapshot")

        # 使用多窗口回退，降低实时统计抖动（1m -> 5m -> 15m -> 60m）
        # Use multi-window fallback to reduce realtime dashboard flicker
        fallback_windows = [1, 5, 15, 60]
        selected_window = 1
        aggregated_data = self._empty_aggregated_data()

        for window_minutes in fallback_windows:
            window_start = end_time - timedelta(minutes=window_minutes)
            candidate = await self._aggregate_from_access_logs(
                window_start,
                end_time,
                dimension_type,
                dimension_value,
            )
            aggregated_data = candidate
            selected_window = window_minutes
            if int(candidate.get('total_requests', 0)) > 0:
                break

        stats = CaddyStats(
            stat_time=self._normalize_time_by_period(end_time, 'minute'),
            stat_period='minute',
            dimension_type=dimension_type,
            dimension_value=dimension_value,
            stats_metadata=RealtimeStatsMetadata(
                realtime_window_minutes=selected_window,
            ).model_dump(),
            **aggregated_data,
        )

        # 缓存实时快照，供后续查询复用
        # Persist snapshot for subsequent quick reads
        return await upsert_stats(stats)

        return latest_stats

    async def get_stats_by_query(self, query: StatsQuery) -> List[CaddyStats]:
        """
        根据查询条件获取统计数据
        
        Args:
            query: 查询参数对象
            
        Returns:
            统计数据列表
        """
        logger.info(f"Querying stats with filters: {query.model_dump()}")
        return await query_stats(query)

    async def get_global_stats_trend(self, stat_period: str, hours: int = 24) -> List[CaddyStats]:
        """
        获取全局统计趋势
        
        Args:
            stat_period: 统计周期
            hours: 过去多少小时
            
        Returns:
            统计数据列表
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        stats_list = await get_global_stats(stat_period, start_time, end_time)
        if stats_list:
            return stats_list

        logger.info("No pre-aggregated global trend found, fallback to access logs aggregation")
        distribution = await get_timeseries_distribution(stat_period, start_time, end_time)
        return self._build_trend_stats_from_distribution(
            distribution=distribution,
            stat_period=stat_period,
            dimension_type="global",
            dimension_value="",
        )

    async def get_service_stats_trend(self, service: str, stat_period: str, hours: int = 24) -> List[CaddyStats]:
        """
        获取服务级别统计趋势
        
        Args:
            service: 服务名称
            stat_period: 统计周期
            hours: 过去多少小时
            
        Returns:
            统计数据列表
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        stats_list = await get_service_stats(service, stat_period, start_time, end_time)
        if stats_list:
            return stats_list

        logger.info("No pre-aggregated service trend found, fallback to access logs aggregation: %s", service)
        distribution = await get_timeseries_distribution(
            stat_period=stat_period,
            start_time=start_time,
            end_time=end_time,
            upstream_service=service,
        )
        return self._build_trend_stats_from_distribution(
            distribution=distribution,
            stat_period=stat_period,
            dimension_type="service",
            dimension_value=service,
        )

    async def get_route_stats_trend(self, route: str, stat_period: str, hours: int = 24) -> List[CaddyStats]:
        """
        获取路由级别统计趋势
        
        Args:
            route: 路由名称
            stat_period: 统计周期
            hours: 过去多少小时
            
        Returns:
            统计数据列表
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        stats_list = await get_route_stats(route, stat_period, start_time, end_time)
        if stats_list:
            return stats_list

        logger.info("No pre-aggregated route trend found, fallback to access logs aggregation: %s", route)
        distribution = await get_timeseries_distribution(
            stat_period=stat_period,
            start_time=start_time,
            end_time=end_time,
            matched_route=route,
        )
        return self._build_trend_stats_from_distribution(
            distribution=distribution,
            stat_period=stat_period,
            dimension_type="route",
            dimension_value=route,
        )

    def _build_trend_stats_from_distribution(
            self,
            distribution: List[Dict[str, Any]],
            stat_period: str,
            dimension_type: str,
            dimension_value: Optional[str],
    ) -> List[CaddyStats]:
        """将访问日志聚合结果转换为 CaddyStats 趋势序列
        Convert access-log aggregation results to CaddyStats trend list
        """
        trend_list: List[CaddyStats] = []
        for item in distribution:
            bucket_time = item.get("bucket_time")
            if not bucket_time:
                continue

            trend_list.append(
                CaddyStats(
                    stat_time=bucket_time,
                    stat_period=stat_period,
                    dimension_type=dimension_type,
                    dimension_value=dimension_value,
                    total_requests=int(item.get("total_requests", 0)),
                    success_requests=int(item.get("success_requests", 0)),
                    client_error_requests=int(item.get("client_error_requests", 0)),
                    server_error_requests=int(item.get("server_error_requests", 0)),
                    total_bytes_sent=int(item.get("total_bytes_sent", 0)),
                    total_bytes_received=0,
                    avg_response_time=item.get("avg_response_time"),
                    min_response_time=item.get("min_response_time"),
                    max_response_time=item.get("max_response_time"),
                    p50_response_time=item.get("p50_response_time"),
                    p95_response_time=item.get("p95_response_time"),
                    p99_response_time=item.get("p99_response_time"),
                    waf_blocked_requests=int(item.get("waf_blocked_requests", 0)),
                    waf_logged_requests=int(item.get("waf_logged_requests", 0)),
                    rate_limited_requests=int(item.get("rate_limited_requests", 0)),
                    tls_requests=int(item.get("tls_requests", 0)),
                    non_tls_requests=int(item.get("non_tls_requests", 0)),
                    unique_ips=int(item.get("unique_ips", 0)),
                    unique_user_agents=int(item.get("unique_user_agents", 0)),
                )
            )

        return trend_list

    async def get_top_countries(
            self,
            stat_period: str = 'hour',
            limit: int = 20,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> List[CaddyStats]:
        """
        获取访问量 Top N 的国家
        
        Args:
            stat_period: 统计周期
            limit: 返回数量
            
        Returns:
            国家统计列表
        """
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(hours=1)
        distribution = await get_country_distribution(start_time, end_time)

        stat_time = self._normalize_time_by_period(end_time, stat_period)
        total_requests = sum(int(item.get("count", 0)) for item in distribution)
        denominator = total_requests if total_requests > 0 else 1
        top_items: List[CaddyStats] = []
        for item in distribution[:limit]:
            country = item.get("country") or "Unknown"
            country_code = item.get("country_code") or "UNKNOWN"
            count = int(item.get("count", 0))
            percentage = round((count / denominator) * 100, 2)
            top_items.append(
                CaddyStats(
                    stat_time=stat_time,
                    stat_period=stat_period,
                    dimension_type="country",
                    dimension_value=country,
                    total_requests=count,
                    success_requests=0,
                    client_error_requests=0,
                    server_error_requests=0,
                    total_bytes_sent=0,
                    total_bytes_received=0,
                    waf_blocked_requests=0,
                    waf_logged_requests=0,
                    rate_limited_requests=0,
                    tls_requests=0,
                    non_tls_requests=0,
                    unique_ips=0,
                    unique_user_agents=0,
                    avg_response_time=0,
                    min_response_time=0,
                    max_response_time=0,
                    p50_response_time=0,
                    p95_response_time=0,
                    p99_response_time=0,
                    stats_metadata=TopCountryStatsMetadata(
                        country=country,
                        country_name=country,
                        country_code=country_code,
                        count=count,
                        percentage=percentage,
                    ).model_dump(),
                )
            )

        return top_items

    async def get_top_ips(
            self,
            stat_period: str = 'hour',
            limit: int = 20,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> List[CaddyStats]:
        """
        获取访问量 Top N 的 IP
        
        Args:
            stat_period: 统计周期
            limit: 返回数量
            
        Returns:
            IP 统计列表
        """
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(hours=1)
        distribution = await get_ip_distribution(start_time, end_time)

        stat_time = self._normalize_time_by_period(end_time, stat_period)
        total_requests = sum(int(item.get("count", 0)) for item in distribution)
        denominator = total_requests if total_requests > 0 else 1
        top_items: List[CaddyStats] = []
        for item in distribution[:limit]:
            client_ip = item.get("client_ip") or "unknown"
            country = item.get("country") or "Unknown"
            city = item.get("city") or "Unknown"
            count = int(item.get("count", 0))
            percentage = round((count / denominator) * 100, 2)
            top_items.append(
                CaddyStats(
                    stat_time=stat_time,
                    stat_period=stat_period,
                    dimension_type="ip",
                    dimension_value=client_ip,
                    total_requests=count,
                    success_requests=0,
                    client_error_requests=0,
                    server_error_requests=0,
                    total_bytes_sent=0,
                    total_bytes_received=0,
                    waf_blocked_requests=0,
                    waf_logged_requests=0,
                    rate_limited_requests=0,
                    tls_requests=0,
                    non_tls_requests=0,
                    unique_ips=0,
                    unique_user_agents=0,
                    avg_response_time=0,
                    min_response_time=0,
                    max_response_time=0,
                    p50_response_time=0,
                    p95_response_time=0,
                    p99_response_time=0,
                    stats_metadata=TopIPStatsMetadata(
                        client_ip=client_ip,
                        country=country,
                        city=city,
                        count=count,
                        percentage=percentage,
                    ).model_dump(),
                )
            )

        return top_items

    async def cleanup_old_stats(self, days: int = 90) -> int:
        """
        清理旧的统计数据
        
        业务规则：保留最近 N 天的统计数据
        
        Args:
            days: 保留天数
            
        Returns:
            删除的记录数
        """
        logger.info(f"Cleaning up stats older than {days} days")

        before_time = datetime.now(timezone.utc) - timedelta(days=days)
        deleted_count = await delete_old_stats(before_time)

        logger.info(f"Cleaned up {deleted_count} old stats records")
        return deleted_count

    async def _aggregate_from_access_logs(
            self,
            start_time: datetime,
            end_time: datetime,
            dimension_type: str,
            dimension_value: Optional[str]
    ) -> Dict[str, Any]:
        """
        从访问日志聚合统计数据
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            dimension_type: 维度类型
            dimension_value: 维度值
            
        Returns:
            聚合数据字典
        """
        from cancan_microstack.public.schemas.caddy import AccessLogQuery

        # 构建查询条件
        query = AccessLogQuery(
            start_time=start_time,
            end_time=end_time,
            limit=1000  # 限制查询数量（Pydantic 最大值为 1000）
        )

        # 根据维度类型添加过滤条件
        if dimension_type == 'service' and dimension_value:
            query.upstream_service = dimension_value
        elif dimension_type == 'route' and dimension_value:
            query.matched_route = dimension_value
        elif dimension_type == 'ip' and dimension_value:
            query.client_ip = dimension_value
        elif dimension_type == 'country' and dimension_value:
            query.country = dimension_value

        # 查询访问日志
        logs = await query_access_logs(query)

        if logs:
            # 只过滤系统内部请求；保留用户本机发起的正常访问请求
            # Only filter system-internal traffic; keep normal user-origin requests
            logs = [log for log in logs if not self._is_system_internal_request(log.path)]

        if not logs:
            return self._empty_aggregated_data()

        # 聚合计算
        total_requests = len(logs)
        success_requests = sum(1 for log in logs if 200 <= log.status_code < 400)
        client_error_requests = sum(1 for log in logs if 400 <= log.status_code < 500)
        server_error_requests = sum(1 for log in logs if 500 <= log.status_code < 600)

        total_bytes_sent = sum(log.response_size for log in logs if log.response_size)

        response_times = [log.response_time for log in logs if log.response_time is not None]

        waf_blocked = sum(1 for log in logs if log.waf_action == 'block')
        waf_logged = sum(1 for log in logs if log.waf_action == 'log')
        rate_limited = sum(1 for log in logs if log.rate_limited)

        tls_requests = sum(1 for log in logs if log.tls_version)
        non_tls_requests = total_requests - tls_requests

        unique_ips = len(set(log.client_ip for log in logs))
        unique_user_agents = len(set(log.user_agent for log in logs if log.user_agent))

        return StatsAggregationPayload(
            total_requests=total_requests,
            success_requests=success_requests,
            client_error_requests=client_error_requests,
            server_error_requests=server_error_requests,
            total_bytes_sent=total_bytes_sent,
            total_bytes_received=0,
            avg_response_time=int(sum(response_times) / len(response_times)) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            p50_response_time=self._calculate_percentile(response_times, 50) if response_times else 0,
            p95_response_time=self._calculate_percentile(response_times, 95) if response_times else 0,
            p99_response_time=self._calculate_percentile(response_times, 99) if response_times else 0,
            waf_blocked_requests=waf_blocked,
            waf_logged_requests=waf_logged,
            rate_limited_requests=rate_limited,
            tls_requests=tls_requests,
            non_tls_requests=non_tls_requests,
            unique_ips=unique_ips,
            unique_user_agents=unique_user_agents,
        ).to_stats_dict()

    def _calculate_percentile(self, values: List[int], percentile: int) -> int:
        """
        计算百分位数
        
        Args:
            values: 数值列表
            percentile: 百分位（0-100）
            
        Returns:
            百分位数值
        """
        if not values:
            return 0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _normalize_time_by_period(self, time: datetime, period: str) -> datetime:
        """
        根据统计周期标准化时间
        
        Args:
            time: 原始时间
            period: 统计周期
            
        Returns:
            标准化后的时间
        """
        if period == 'minute':
            return time.replace(second=0, microsecond=0)
        elif period == 'hour':
            return time.replace(minute=0, second=0, microsecond=0)
        elif period == 'day':
            return time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'month':
            return time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return time

    def _empty_aggregated_data(self) -> Dict[str, Any]:
        """返回空的聚合数据"""
        return StatsAggregationPayload().to_stats_dict()

    def _validate_stat_period(self, stat_period: str):
        """
        验证统计周期
        
        Args:
            stat_period: 统计周期
            
        Raises:
            ValueError: 周期无效
        """
        valid_periods = ['minute', 'hour', 'day', 'month']
        if stat_period not in valid_periods:
            raise ValueError(f"Invalid stat period: {stat_period}. Must be one of {valid_periods}")

    def _validate_dimension_type(self, dimension_type: str):
        """
        验证维度类型
        
        Args:
            dimension_type: 维度类型
            
        Raises:
            ValueError: 维度类型无效
        """
        valid_dimensions = ['global', 'service', 'route', 'ip', 'country']
        if dimension_type not in valid_dimensions:
            raise ValueError(f"Invalid dimension type: {dimension_type}. Must be one of {valid_dimensions}")

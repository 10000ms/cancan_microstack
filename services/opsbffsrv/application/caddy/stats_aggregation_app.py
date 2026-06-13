"""
Caddy 统计数据应用服务
协调统计数据聚合和查询的业务流程
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

from cancan_microstack.public.schemas.caddy import (
    CaddyStats,
    StatsQuery,
)
from cancan_microstack.services.opsbffsrv.domain.caddy.stats_aggregation import StatsAggregationDomain


class StatsAggregationApp:
    """统计数据应用服务"""

    def __init__(self):
        self.domain = StatsAggregationDomain()

    @staticmethod
    def _parse_optional_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
        """解析可选时间字符串（ISO 8601）
        Parse optional ISO-8601 datetime string to timezone-aware datetime
        """
        if not datetime_str:
            return None

        parsed = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    async def get_realtime_global_stats(self) -> Optional[CaddyStats]:
        """
        获取全局实时统计数据
        
        Returns:
            统计对象或 None
        """
        logger.info("Fetching realtime global stats")
        return await self.domain.get_realtime_stats('global')

    async def get_realtime_service_stats(self, service: str) -> Optional[CaddyStats]:
        """
        获取服务级别实时统计数据
        
        Args:
            service: 服务名称
            
        Returns:
            统计对象或 None
        """
        logger.info(f"Fetching realtime stats for service: {service}")
        return await self.domain.get_realtime_stats('service', service)

    async def query_stats(self, query: StatsQuery) -> List[CaddyStats]:
        """
        查询统计数据
        
        Args:
            query: 查询参数
            
        Returns:
            统计数据列表
        """
        logger.info(f"Querying stats")
        return await self.domain.get_stats_by_query(query)

    async def get_global_trend(
            self,
            period: str = 'hourly',
            start_time: Optional[str] = None,
            end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取全局统计趋势
        
        Args:
            period: 统计周期（hourly/daily/monthly）
            start_time: 开始时间（ISO 8601格式）
            end_time: 结束时间（ISO 8601格式）
            
        Returns:
            趋势数据
        """
        # 映射周期名称
        stat_period = 'hour' if period == 'hourly' else ('day' if period == 'daily' else 'month')

        # 计算时间范围（如果未提供）
        hours = 24 if period == 'hourly' else (7 * 24 if period == 'daily' else 30 * 24)

        logger.info(f"Fetching global trend: period={stat_period}, hours={hours}")

        try:
            stats_list = await self.domain.get_global_stats_trend(stat_period, hours)

            return {
                "status": "success",
                "period": period,
                "hours": hours,
                "data": stats_list
            }
        except Exception as e:
            logger.error(f"Error fetching global trend: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_service_trend(
            self,
            service_name: str,
            period: str = 'hourly',
            start_time: Optional[str] = None,
            end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取服务级别统计趋势
        
        Args:
            service_name: 服务名称
            period: 统计周期（hourly/daily/monthly）
            start_time: 开始时间（ISO 8601格式）
            end_time: 结束时间（ISO 8601格式）
            
        Returns:
            趋势数据
        """
        # 映射周期名称
        stat_period = 'hour' if period == 'hourly' else ('day' if period == 'daily' else 'month')
        hours = 24 if period == 'hourly' else (7 * 24 if period == 'daily' else 30 * 24)

        logger.info(f"Fetching service trend: service={service_name}, period={stat_period}, hours={hours}")

        try:
            stats_list = await self.domain.get_service_stats_trend(service_name, stat_period, hours)

            return {
                "status": "success",
                "service": service_name,
                "period": period,
                "hours": hours,
                "data": stats_list
            }
        except Exception as e:
            logger.error(f"Error fetching service trend: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_route_trend(
            self,
            route_id: int,
            period: str = 'hourly',
            start_time: Optional[str] = None,
            end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取路由级别统计趋势
        
        Args:
            route_id: 路由ID
            period: 统计周期（hourly/daily/monthly）
            start_time: 开始时间（ISO 8601格式）
            end_time: 结束时间（ISO 8601格式）
            
        Returns:
            趋势数据
        """
        # 映射周期名称
        stat_period = 'hour' if period == 'hourly' else ('day' if period == 'daily' else 'month')
        hours = 24 if period == 'hourly' else (7 * 24 if period == 'daily' else 30 * 24)

        # 将 route_id 转换为字符串，因为 domain 层期望路由名称
        route = str(route_id)

        logger.info(f"Fetching route trend: route_id={route_id}, period={stat_period}, hours={hours}")

        try:
            stats_list = await self.domain.get_route_stats_trend(route, stat_period, hours)

            return {
                "status": "success",
                "route_id": route_id,
                "period": period,
                "hours": hours,
                "data": stats_list
            }
        except Exception as e:
            logger.error(f"Error fetching route trend: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_top_countries(
            self,
            limit: int = 10,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取访问量 Top N 的国家
        
        Args:
            limit: 返回数量（默认10）
            start_time: 开始时间（ISO 8601格式）
            end_time: 结束时间（ISO 8601格式）
            
        Returns:
            Top 国家数据
        """
        stat_period = 'hour'  # 默认使用小时统计

        logger.info(f"Fetching top countries: limit={limit}")

        try:
            parsed_start_time = self._parse_optional_datetime(start_time)
            parsed_end_time = self._parse_optional_datetime(end_time)
            top_countries = await self.domain.get_top_countries(
                stat_period=stat_period,
                limit=limit,
                start_time=parsed_start_time,
                end_time=parsed_end_time,
            )

            return {
                "status": "success",
                "period": stat_period,
                "data": top_countries
            }
        except Exception as e:
            logger.error(f"Error fetching top countries: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_top_ips(
            self,
            limit: int = 10,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取访问量 Top N 的 IP
        
        Args:
            limit: 返回数量（默认10）
            start_time: 开始时间（ISO 8601格式）
            end_time: 结束时间（ISO 8601格式）
            
        Returns:
            Top IP 数据
        """
        stat_period = 'hour'  # 默认使用小时统计

        logger.info(f"Fetching top IPs: limit={limit}")

        try:
            parsed_start_time = self._parse_optional_datetime(start_time)
            parsed_end_time = self._parse_optional_datetime(end_time)
            top_ips = await self.domain.get_top_ips(
                stat_period=stat_period,
                limit=limit,
                start_time=parsed_start_time,
                end_time=parsed_end_time,
            )

            return {
                "status": "success",
                "period": stat_period,
                "data": top_ips
            }
        except Exception as e:
            logger.error(f"Error fetching top IPs: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def aggregate_stats_now(
            self,
            stat_period: str,
            dimension_type: str,
            dimension_value: Optional[str] = None,
            hours: int = 1
    ) -> Dict[str, Any]:
        """
        立即聚合统计数据（手动触发）
        
        Args:
            stat_period: 统计周期
            dimension_type: 维度类型
            dimension_value: 维度值
            hours: 聚合过去多少小时的数据
            
        Returns:
            聚合结果
        """
        logger.info(f"Manually aggregating stats: period={stat_period}, dimension={dimension_type}")

        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)

            stats = await self.domain.aggregate_stats_for_period(
                start_time, end_time, stat_period, dimension_type, dimension_value
            )

            return {
                "status": "success",
                "stats": stats
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error aggregating stats: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def cleanup_old_stats(self, days: int = 90) -> Dict[str, Any]:
        """
        清理旧的统计数据
        
        Args:
            days: 保留天数
            
        Returns:
            清理结果
        """
        logger.info(f"Cleaning up stats older than {days} days")

        try:
            deleted_count = await self.domain.cleanup_old_stats(days)

            return {
                "status": "success",
                "message": f"Deleted {deleted_count} old stats records"
            }
        except Exception as e:
            logger.error(f"Error cleaning up stats: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

"""
Caddy 访问日志应用服务
协调访问日志接收、查询和分析的业务流程
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from datetime import datetime
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyAccessLog, AccessLogQuery
from cancan_microstack.services.opsbffsrv.domain.caddy.access_log_analysis import AccessLogAnalysisDomain


class AccessLogAnalysisApp:
    """访问日志应用服务"""

    def __init__(self):
        self.domain = AccessLogAnalysisDomain()

    async def ingest_single_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收单条访问日志
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            结果字典
        """
        logger.debug("Ingesting single access log")

        try:
            log_entry = await self.domain.ingest_log_entry(log_data)

            return {
                "status": "success",
                "log": log_entry
            }
        except ValueError as e:
            logger.warning(f"Log ingestion failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error ingesting log: {e}", exc_info=True)
            return {
                "status": "error",
                "error": "Internal server error"
            }

    async def ingest_batch_logs(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        批量接收访问日志
        
        Args:
            log_lines: JSON 格式的日志行列表
            
        Returns:
            结果字典
        """
        logger.info(f"Ingesting batch of {len(log_lines)} logs")

        try:
            ingested_count = await self.domain.ingest_log_batch(log_lines)

            return {
                "status": "success",
                "message": f"Successfully ingested {ingested_count} logs",
                "count": ingested_count
            }
        except Exception as e:
            logger.error(f"Error ingesting batch logs: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def search_logs(self, query: AccessLogQuery) -> List[CaddyAccessLog]:
        """
        搜索访问日志
        
        Args:
            query: 查询参数
            
        Returns:
            访问日志列表
        """
        logger.info("Searching access logs")

        try:
            return await self.domain.search_logs(query)
        except ValueError as e:
            logger.warning(f"Invalid query parameters: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching logs: {e}", exc_info=True)
            return []

    async def get_log_details(self, log_id: int) -> Optional[CaddyAccessLog]:
        """
        获取访问日志详情
        
        Args:
            log_id: 日志 ID
            
        Returns:
            访问日志对象或 None
        """
        return await self.domain.get_log_details(log_id)

    async def get_log_by_request_id(self, request_id: str) -> Optional[CaddyAccessLog]:
        """
        根据请求 ID 获取访问日志
        
        Args:
            request_id: 请求 ID
            
        Returns:
            访问日志对象或 None
        """
        return await self.domain.get_log_by_request_id(request_id)

    async def get_logs_for_ip(self, client_ip: str, limit: int = 100) -> List[CaddyAccessLog]:
        """
        获取指定 IP 的访问日志
        
        Args:
            client_ip: 客户端 IP
            limit: 返回数量限制
            
        Returns:
            访问日志列表
        """
        return await self.domain.get_logs_for_ip(client_ip, limit)

    async def get_logs_for_service(self, service: str, limit: int = 100) -> List[CaddyAccessLog]:
        """
        获取指定服务的访问日志
        
        Args:
            service: 服务名称
            limit: 返回数量限制
            
        Returns:
            访问日志列表
        """
        return await self.domain.get_logs_for_service(service, limit)

    async def get_security_events(self, event_type: str = 'waf_blocked', limit: int = 100) -> Dict[str, Any]:
        """
        获取安全事件日志
        
        Args:
            event_type: 事件类型（waf_blocked/rate_limited）
            limit: 返回数量限制
            
        Returns:
            安全事件数据
        """
        logger.info(f"Fetching security events: {event_type}")

        try:
            events = await self.domain.get_security_events(event_type, limit)

            return {
                "status": "success",
                "event_type": event_type,
                "count": len(events),
                "data": events
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error fetching security events: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def analyze_geographic_distribution(
            self,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        分析访问的地理分布
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            地理分布数据
        """
        logger.info("Analyzing geographic distribution")

        try:
            distribution = await self.domain.analyze_geographic_distribution(start_time, end_time)

            return {
                "status": "success",
                "data": distribution
            }
        except Exception as e:
            logger.error(f"Error analyzing geographic distribution: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def analyze_status_code_distribution(
            self,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        分析 HTTP 状态码分布
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            状态码分布数据
        """
        logger.info("Analyzing status code distribution")

        try:
            distribution = await self.domain.analyze_status_code_distribution(start_time, end_time)

            return {
                "status": "success",
                "data": distribution
            }
        except Exception as e:
            logger.error(f"Error analyzing status code distribution: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def detect_suspicious_ips(
            self,
            time_window: int = 60,
            request_threshold: int = 1000
    ) -> Dict[str, Any]:
        """
        检测可疑 IP（高频访问）
        
        Args:
            time_window: 时间窗口（分钟）
            request_threshold: 请求数阈值
            
        Returns:
            可疑 IP 数据
        """
        logger.info(f"Detecting suspicious IPs: window={time_window}min, threshold={request_threshold}")

        try:
            suspicious_ips = await self.domain.detect_suspicious_ips(time_window, request_threshold)

            return {
                "status": "success",
                "count": len(suspicious_ips),
                "data": suspicious_ips
            }
        except Exception as e:
            logger.error(f"Error detecting suspicious IPs: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def analyze_error_patterns(self, hours: int = 24) -> Dict[str, Any]:
        """
        分析错误模式
        
        Args:
            hours: 过去多少小时
            
        Returns:
            错误分析结果
        """
        logger.info(f"Analyzing error patterns for the past {hours} hours")

        try:
            error_analysis = await self.domain.analyze_error_patterns(hours)

            # domain 返回 ErrorPatternAnalysis (pydantic)，需先 model_dump 才能展开
            return {
                "status": "success",
                **error_analysis.model_dump()
            }
        except Exception as e:
            logger.error(f"Error analyzing error patterns: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def cleanup_old_logs(self, days: int = 30) -> Dict[str, Any]:
        """
        清理旧的访问日志
        
        Args:
            days: 保留天数
            
        Returns:
            清理结果
        """
        logger.info(f"Cleaning up logs older than {days} days")

        try:
            deleted_count = await self.domain.cleanup_old_logs(days)

            return {
                "status": "success",
                "message": f"Deleted {deleted_count} old access log records"
            }
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_log_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        获取日志数量
        
        Args:
            filters: 过滤条件
            
        Returns:
            日志数量
        """
        return await self.domain.get_log_count(filters)

"""
Caddy 访问日志解析器
解析 Caddy JSON 格式的访问日志并提取关键信息
"""
from typing import (
    Any,
    Dict,
    Optional,
)
import json
from datetime import datetime, timezone
from nanoid import generate
from linglong_web.utils import logger
from cancan_microstack.public.schemas.caddy import CaddyAccessLog
from cancan_microstack.services.opsbffsrv.infrastructure.caddy.ip_geo_locator import ip_geo_locator


class AccessLogParser:
    """访问日志解析器"""

    @staticmethod
    def parse_json_log(log_line: str) -> Optional[CaddyAccessLog]:
        """
        解析 JSON 格式的访问日志行
        
        Args:
            log_line: JSON 格式的日志行
            
        Returns:
            访问日志对象或 None
        """
        try:
            log_data = json.loads(log_line)
            return AccessLogParser._build_access_log(log_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON log: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Error parsing access log: {e}", exc_info=True)
            return None

    @staticmethod
    def parse_dict_log(log_data: Dict[str, Any]) -> Optional[CaddyAccessLog]:
        """
        解析字典格式的访问日志
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            访问日志对象或 None
        """
        try:
            return AccessLogParser._build_access_log(log_data)
        except Exception as e:
            logger.error(f"Error parsing access log dict: {e}", exc_info=True)
            return None

    @staticmethod
    def _build_access_log(log_data: Dict[str, Any]) -> CaddyAccessLog:
        """
        从日志数据构建 CaddyAccessLog 对象
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            访问日志对象
        """
        # 提取基础信息
        request = log_data.get("request", {})
        response = log_data.get("resp_headers", {})

        # 提取客户端 IP（处理代理情况）
        client_ip = AccessLogParser._extract_client_ip(log_data)

        # 提取请求 ID（优先使用 X-Linglong-Reqid，其次 X-Request-Id）
        # Extract request ID preferring X-Linglong-Reqid, then X-Request-Id
        request_id = (
            log_data.get("request_id")
            or response.get("X-Linglong-Reqid", [None])[0]
            or response.get("X-Request-Id", [None])[0]
            or generate()
        )

        # 提取时间戳
        timestamp_str = log_data.get("ts") or log_data.get("timestamp")
        timestamp = AccessLogParser._parse_timestamp(timestamp_str)

        # 提取路径和查询字符串
        uri = request.get("uri", "")
        path, query_string = AccessLogParser._split_uri(uri)

        # 获取 IP 地理位置信息
        geo_info = ip_geo_locator.lookup(client_ip) if client_ip else {}

        # 提取 WAF 信息
        waf_action = log_data.get("waf_action")
        waf_rule_id = log_data.get("waf_rule_id")
        waf_score = log_data.get("waf_score")

        # 提取限流信息
        rate_limited = log_data.get("rate_limited", False)
        rate_limit_rule = log_data.get("rate_limit_rule")

        # 提取上游信息
        upstream_info = log_data.get("upstream", {})

        # 提取 TLS 信息
        tls_info = request.get("tls", {})

        # 构建访问日志对象
        return CaddyAccessLog(
            request_id=request_id,
            timestamp=timestamp,
            client_ip=client_ip,
            client_port=AccessLogParser._extract_client_port(log_data),
            user_agent=request.get("headers", {}).get("User-Agent", [None])[0],
            referer=request.get("headers", {}).get("Referer", [None])[0],
            country=geo_info.get("country"),
            country_code=geo_info.get("country_code"),
            region=geo_info.get("region"),
            city=geo_info.get("city"),
            latitude=geo_info.get("latitude"),
            longitude=geo_info.get("longitude"),
            timezone=geo_info.get("timezone"),
            isp=geo_info.get("isp"),
            method=request.get("method", "GET"),
            protocol=request.get("proto", "HTTP/1.1"),
            host=request.get("host"),
            path=path,
            query_string=query_string,
            matched_route=log_data.get("matched_route"),
            upstream_service=upstream_info.get("service"),
            upstream_host=upstream_info.get("host"),
            upstream_port=upstream_info.get("port"),
            status_code=log_data.get("status", 0),
            response_size=log_data.get("size"),
            response_time=AccessLogParser._parse_duration(log_data.get("duration")),
            waf_action=waf_action,
            waf_rule_id=waf_rule_id,
            waf_score=waf_score,
            rate_limited=rate_limited,
            rate_limit_rule=rate_limit_rule,
            tls_version=tls_info.get("version"),
            tls_cipher=tls_info.get("cipher_suite"),
            log_metadata=AccessLogParser._extract_log_metadata(log_data),
        )

    @staticmethod
    def _extract_client_ip(log_data: Dict[str, Any]) -> str:
        """
        提取客户端真实 IP
        
        优先级：X-Forwarded-For > X-Real-IP > remote_ip
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            客户端 IP
        """
        request = log_data.get("request", {})
        headers = request.get("headers", {})

        # 检查 X-Forwarded-For
        x_forwarded_for = headers.get("X-Forwarded-For", [None])[0]
        if x_forwarded_for:
            # 取第一个 IP（客户端真实 IP）
            return x_forwarded_for.split(',')[0].strip()

        # 检查 X-Real-IP
        x_real_ip = headers.get("X-Real-IP", [None])[0]
        if x_real_ip:
            return x_real_ip

        # 使用 remote_ip
        return request.get("remote_ip", "unknown")

    @staticmethod
    def _extract_client_port(log_data: Dict[str, Any]) -> Optional[int]:
        """
        提取客户端端口
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            客户端端口或 None
        """
        try:
            remote_port = log_data.get("request", {}).get("remote_port")
            if remote_port is not None:
                return int(remote_port)

            remote_addr = log_data.get("request", {}).get("remote_addr", "")
            if ':' in remote_addr:
                return int(remote_addr.split(':')[-1])
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_timestamp(timestamp_str: Optional[str]) -> datetime:
        """
        解析时间戳字符串
        
        Args:
            timestamp_str: 时间戳字符串
            
        Returns:
            datetime 对象
        """
        if not timestamp_str:
            return datetime.now(timezone.utc)

        try:
            # Caddy 使用 Unix 时间戳（秒）
            if isinstance(timestamp_str, (int, float)):
                return datetime.fromtimestamp(timestamp_str, tz=timezone.utc)

            # 尝试解析 ISO 格式
            parsed = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return datetime.now(timezone.utc)

    @staticmethod
    def _parse_duration(duration_str: Optional[Any]) -> Optional[int]:
        """
        解析持续时间字符串（转换为毫秒）
        
        Args:
            duration_str: 持续时间字符串（如 "0.123s" 或 123000000 纳秒）
            
        Returns:
            毫秒数或 None
        """
        if not duration_str:
            return None

        try:
            # Caddy 常见格式：float 秒（如 0.0123）
            if isinstance(duration_str, float):
                return int(duration_str * 1000)

            # 整数格式：兼容纳秒与毫秒
            if isinstance(duration_str, int):
                if duration_str > 1_000_000:
                    return duration_str // 1_000_000  # 纳秒转毫秒
                return duration_str

            # 如果是字符串（如 "0.123s"）
            if isinstance(duration_str, str):
                if duration_str.endswith('s'):
                    seconds = float(duration_str[:-1])
                    return int(seconds * 1000)
                elif duration_str.endswith('ms'):
                    return int(float(duration_str[:-2]))
        except Exception as e:
            logger.warning(f"Failed to parse duration '{duration_str}': {e}")

        return None

    @staticmethod
    def _split_uri(uri: str) -> tuple:
        """
        分割 URI 为路径和查询字符串
        
        Args:
            uri: 完整 URI
            
        Returns:
            (path, query_string) 元组
        """
        if '?' in uri:
            parts = uri.split('?', 1)
            return parts[0], parts[1]
        return uri, None

    @staticmethod
    def _extract_log_metadata(log_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        提取额外的元数据
        
        Args:
            log_data: 日志数据字典
            
        Returns:
            元数据字典或 None
        """
        log_metadata = {}

        # 提取自定义字段
        custom_fields = ["user_id", "session_id", "trace_id", "span_id"]
        for field in custom_fields:
            if field in log_data:
                log_metadata[field] = log_data[field]

        return log_metadata if log_metadata else None


# 全局实例
access_log_parser = AccessLogParser()

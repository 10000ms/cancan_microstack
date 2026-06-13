"""
IP 地理位置查询模块
使用 GeoLite2 数据库进行 IP 地址地理定位
"""
from typing import (
    Optional,
    Dict,
    Any,
)
from decimal import Decimal
import os
import geoip2.database
import geoip2.errors

from linglong_web.utils import logger


class IPGeoLocator:
    """IP 地理位置查询器"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 IP 地理位置查询器
        
        Args:
            db_path: GeoLite2 数据库文件路径（可选，默认自动检测）
        """
        self.db_path = db_path or self._auto_detect_db_path()
        self._reader: Optional[geoip2.database.Reader] = None
        self._initialize_reader()

    def _auto_detect_db_path(self) -> str:
        """
        自动检测 GeoIP 数据库路径
        
        优先级：
        1. /usr/share/GeoIP/GeoLite2-City.mmdb (in-pod, Docker 容器内)
        2. {PROJECT_ROOT}/builds/caddy/geoip/GeoLite2-City.mmdb (out-pod, 本地开发)
        """
        # 优先使用容器内路径（in-pod）
        container_path = "/usr/share/GeoIP/GeoLite2-City.mmdb"
        if os.path.exists(container_path):
            return container_path

        # 使用项目路径（out-pod）
        # 获取项目根目录：当前文件是 src/service/opsbffsrv/infrastructure/caddy/ip_geo_locator.py
        # 向上 6 层到达项目根目录
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[5]
        project_path = os.path.join(
            str(project_root),
            "builds/caddy/geoip/GeoLite2-City.mmdb"
        )
        return project_path

    def _initialize_reader(self):
        """初始化数据库读取器"""
        try:
            if not os.path.exists(self.db_path):
                logger.warning(f"GeoIP database file not found: {self.db_path} (IP geolocation will be disabled)")
                self._reader = None
                return

            self._reader = geoip2.database.Reader(self.db_path)
            logger.info(f"GeoIP database initialized: {self.db_path}")
        except Exception as e:
            logger.warning(f"Failed to initialize GeoIP database: {e} (IP geolocation will be disabled)")
            self._reader = None

    def lookup(self, ip_address: str) -> Dict[str, Any]:
        """
        查询 IP 地址的地理位置信息
        
        Args:
            ip_address: IP 地址
            
        Returns:
            地理位置信息字典
        """
        if not self._reader:
            logger.warning("GeoIP reader not initialized")
            return self._empty_result()

        try:
            response = self._reader.city(ip_address)

            return {
                "country": response.country.names.get('zh-CN') or response.country.names.get('en'),
                "country_code": response.country.iso_code,
                "region": response.subdivisions.most_specific.names.get(
                    'zh-CN') or response.subdivisions.most_specific.names.get('en') if response.subdivisions else None,
                "city": response.city.names.get('zh-CN') or response.city.names.get('en'),
                "latitude": Decimal(str(response.location.latitude)) if response.location.latitude else None,
                "longitude": Decimal(str(response.location.longitude)) if response.location.longitude else None,
                "timezone": response.location.time_zone,
                "isp": None,  # GeoLite2-City 不包含 ISP 信息，需要 GeoLite2-ASN
            }
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP address not found in GeoIP database: {ip_address}")
            return self._empty_result()
        except Exception as e:
            logger.error(f"Error looking up IP {ip_address}: {e}", exc_info=True)
            return self._empty_result()

    def lookup_with_asn(self, ip_address: str, asn_db_path: str = "/usr/share/GeoIP/GeoLite2-ASN.mmdb") -> Dict[
        str, Any]:
        """
        查询 IP 地址的地理位置和 ISP 信息
        
        Args:
            ip_address: IP 地址
            asn_db_path: GeoLite2-ASN 数据库路径
            
        Returns:
            包含 ISP 信息的地理位置字典
        """
        # 获取基础地理信息
        geo_info = self.lookup(ip_address)

        # 获取 ISP 信息
        try:
            with geoip2.database.Reader(asn_db_path) as asn_reader:
                response = asn_reader.asn(ip_address)
                geo_info["isp"] = response.autonomous_system_organization
        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"ASN information not found for IP: {ip_address}")
        except Exception as e:
            logger.error(f"Error looking up ASN for IP {ip_address}: {e}", exc_info=True)

        return geo_info

    def _empty_result(self) -> Dict[str, Any]:
        """
        返回空结果
        
        Returns:
            空的地理位置信息字典
        """
        return {
            "country": None,
            "country_code": None,
            "region": None,
            "city": None,
            "latitude": None,
            "longitude": None,
            "timezone": None,
            "isp": None,
        }

    def is_private_ip(self, ip_address: str) -> bool:
        """
        判断是否为私有 IP 地址
        
        Args:
            ip_address: IP 地址
            
        Returns:
            是否为私有 IP
        """
        try:
            import ipaddress
            ip = ipaddress.ip_address(ip_address)
            return ip.is_private
        except Exception as e:
            logger.error(f"Error checking if IP is private: {e}", exc_info=True)
            return False

    def close(self):
        """关闭数据库连接"""
        if self._reader:
            self._reader.close()
            logger.info("GeoIP reader closed")


# 全局实例
ip_geo_locator = IPGeoLocator()

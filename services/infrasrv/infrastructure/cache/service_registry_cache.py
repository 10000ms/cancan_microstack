"""
服务注册 Redis 缓存辅助类
"""
import orjson
from typing import (
    Optional,
    List,
)

from cancan_microstack.public.const.redis import RedisKey
from linglong_web import Rmanager
from linglong_web.utils import logger


class ServiceRegistryCache:
    """服务注册缓存管理"""

    # 缓存过期时间（秒）
    CACHE_TTL_INSTANCE = 60  # 单个实例缓存60秒
    CACHE_TTL_LIST = 30  # 列表缓存30秒

    SERVICE_NAME = "infrasrv"

    @classmethod
    def _get_cache_key(cls, key_template: str, **kwargs) -> str:
        """
        生成缓存 key
        
        Args:
            key_template: key 模板
            **kwargs: 模板参数
        
        Returns:
            完整的缓存 key
        """
        key = key_template.format(**kwargs)
        return f"{cls.SERVICE_NAME}:{RedisKey.SERVICE_REGISTRY_PREFIX}{key}"

    @classmethod
    async def get_instance(cls, service_name: str, instance_id: str) -> Optional[dict]:
        """
        从缓存获取服务实例
        
        Args:
            service_name: 服务名称
            instance_id: 实例ID
        
        Returns:
            服务实例数据，不存在则返回 None
        """
        key = cls._get_cache_key(RedisKey.SERVICE_REGISTRY_INSTANCE, service_name=service_name, instance_id=instance_id)

        try:
            cached_data = await Rmanager.redis().get(key)
            if cached_data:
                return orjson.loads(cached_data)
        except Exception as e:
            logger.error(f"Failed to get cache for instance {service_name}:{instance_id}: {e}")

        return None

    @classmethod
    async def set_instance(cls, service_name: str, instance_id: str, data: dict) -> None:
        """
        缓存服务实例
        
        Args:
            service_name: 服务名称
            instance_id: 实例ID
            data: 实例数据
        """
        key = cls._get_cache_key(RedisKey.SERVICE_REGISTRY_INSTANCE, service_name=service_name, instance_id=instance_id)

        try:
            await Rmanager.redis().setex(
                key,
                cls.CACHE_TTL_INSTANCE,
                orjson.dumps(data)
            )
        except Exception as e:
            logger.error(f"Failed to cache instance {service_name}:{instance_id}: {e}")

    @classmethod
    async def delete_instance(cls, service_name: str, instance_id: str) -> None:
        """
        删除服务实例缓存
        
        Args:
            service_name: 服务名称
            instance_id: 实例ID
        """
        key = cls._get_cache_key(RedisKey.SERVICE_REGISTRY_INSTANCE, service_name=service_name, instance_id=instance_id)

        try:
            await Rmanager.redis().delete(key)
        except Exception as e:
            logger.error(f"Failed to delete cache for instance {service_name}:{instance_id}: {e}")

    @classmethod
    async def get_service_instances(cls, service_name: str) -> Optional[List[dict]]:
        """
        从缓存获取服务的所有实例
        
        Args:
            service_name: 服务名称
        
        Returns:
            实例列表，不存在则返回 None
        """
        key = cls._get_cache_key(RedisKey.SERVICE_REGISTRY_SERVICE_INSTANCES, service_name=service_name)

        try:
            cached_data = await Rmanager.redis().get(key)
            if cached_data:
                return orjson.loads(cached_data)
        except Exception as e:
            logger.error(f"Failed to get cache for service instances {service_name}: {e}")

        return None

    @classmethod
    async def set_service_instances(cls, service_name: str, data: List[dict]) -> None:
        """
        缓存服务的所有实例
        
        Args:
            service_name: 服务名称
            data: 实例列表
        """
        key = cls._get_cache_key(RedisKey.SERVICE_REGISTRY_SERVICE_INSTANCES, service_name=service_name)

        try:
            await Rmanager.redis().setex(
                key,
                cls.CACHE_TTL_LIST,
                orjson.dumps(data)
            )
        except Exception as e:
            logger.error(f"Failed to cache service instances {service_name}: {e}")

    @classmethod
    async def delete_service_instances(cls, service_name: str) -> None:
        """
        删除服务实例列表缓存
        
        Args:
            service_name: 服务名称
        """
        key = cls._get_cache_key(RedisKey.SERVICE_REGISTRY_SERVICE_INSTANCES, service_name=service_name)

        try:
            await Rmanager.redis().delete(key)
        except Exception as e:
            logger.error(f"Failed to delete cache for service instances {service_name}: {e}")

    @classmethod
    async def invalidate_all(cls) -> None:
        """清空所有服务注册相关缓存"""
        try:
            # 使用 SCAN 查找所有匹配的 key
            pattern = f"{cls.SERVICE_NAME}:{RedisKey.SERVICE_REGISTRY_PREFIX}*"
            cursor = 0

            while True:
                cursor, keys = await Rmanager.redis().scan(cursor, match=pattern, count=100)
                if keys:
                    await Rmanager.redis().delete(*keys)

                if cursor == 0:
                    break

            logger.info("All service registry cache invalidated")
        except Exception as e:
            logger.error(f"Failed to invalidate all cache: {e}")

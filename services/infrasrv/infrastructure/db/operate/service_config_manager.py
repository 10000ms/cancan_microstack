"""
服务配置管理器 - 支持 JSON 序列化/反序列化
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
import itertools
import orjson

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, update, delete, and_

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_config import ServiceConfig
from cancan_microstack.services.infrasrv.infrastructure.db.model.service_config_tbl import ServiceConfigTbl
from linglong_web.utils import logger


async def insert_service_config_json(service_name: str, configs: Dict[str, Any]) -> None:
    """
    插入或更新服务配置（配置值自动 JSON 序列化）
    
    Args:
        service_name: 服务名称
        configs: 配置字典 {key: value}，value 会被序列化为 JSON 字符串
    """
    config_list = []
    for key, value in configs.items():
        # 将配置值序列化为 JSON 字符串
        if isinstance(value, str):
            # 如果已经是字符串，尝试解析后再序列化（确保格式统一）
            try:
                parsed = orjson.loads(value)
                json_value = orjson.dumps(parsed).decode('utf-8')
            except orjson.JSONDecodeError:
                # 如果不是有效的 JSON，直接包装为字符串
                json_value = orjson.dumps(value).decode('utf-8')
        else:
            # 其他类型直接序列化
            json_value = orjson.dumps(value).decode('utf-8')

        config_list.append(ServiceConfig(
            service_name=service_name,
            conf_key=key,
            conf_value=json_value
        ))

    async with Rmanager.pg_session() as session:
        batched_iter = itertools.batched(config_list, 500)
        for chunk in batched_iter:
            async with session.begin():
                stmt = insert(ServiceConfigTbl).values(
                    [c.model_dump() for c in chunk]
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["service_name", "conf_key"],
                    set_={'conf_value': stmt.excluded.conf_value}
                )
                await session.execute(stmt)

    logger.info(f"Inserted/Updated {len(config_list)} configs for service {service_name}")


async def get_service_config_json(service_name: str) -> Dict[str, Any]:
    """
    获取服务配置（配置值自动 JSON 反序列化）
    
    Args:
        service_name: 服务名称
    
    Returns:
        配置字典 {key: value}，value 已反序列化
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceConfigTbl).where(
                ServiceConfigTbl.service_name == service_name
            )
            rows = list((await session.execute(stmt)).scalars().all())

    if not rows:
        return {}

    config_dict = {}
    for row in rows:
        try:
            # 反序列化 JSON 字符串
            config_dict[row.conf_key] = orjson.loads(row.conf_value)
        except orjson.JSONDecodeError as e:
            logger.error(f"Failed to parse config {row.conf_key} for service {service_name}: {e}")
            # 失败时保留原始字符串
            config_dict[row.conf_key] = row.conf_value

    return config_dict


async def update_service_config_json(service_name: str, config_key: str, config_value: Any) -> None:
    """
    更新单个服务配置项（配置值自动 JSON 序列化）
    
    Args:
        service_name: 服务名称
        config_key: 配置键
        config_value: 配置值（会被序列化为 JSON）
    """
    # 序列化配置值
    if isinstance(config_value, str):
        try:
            parsed = orjson.loads(config_value)
            json_value = orjson.dumps(parsed).decode('utf-8')
        except orjson.JSONDecodeError:
            json_value = orjson.dumps(config_value).decode('utf-8')
    else:
        json_value = orjson.dumps(config_value).decode('utf-8')

    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(ServiceConfigTbl).where(
                and_(
                    ServiceConfigTbl.service_name == service_name,
                    ServiceConfigTbl.conf_key == config_key,
                )
            ).values(conf_value=json_value)

            result = await session.execute(stmt)

            # 如果没有更新任何行，则插入新记录
            if result.rowcount == 0:
                insert_stmt = insert(ServiceConfigTbl).values(
                    service_name=service_name,
                    conf_key=config_key,
                    conf_value=json_value
                )
                await session.execute(insert_stmt)

    logger.info(f"Updated config {config_key} for service {service_name}")


async def delete_service_config_key(service_name: str, config_key: str) -> bool:
    """
    删除服务配置项
    
    Args:
        service_name: 服务名称
        config_key: 配置键
    
    Returns:
        是否成功删除
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(ServiceConfigTbl).where(
                and_(
                    ServiceConfigTbl.service_name == service_name,
                    ServiceConfigTbl.conf_key == config_key,
                )
            )
            result = await session.execute(stmt)
            success = result.rowcount > 0

    if success:
        logger.info(f"Deleted config {config_key} for service {service_name}")
    else:
        logger.warning(f"Config {config_key} not found for service {service_name}")

    return success


async def get_all_service_configs_json() -> Dict[str, Dict[str, Any]]:
    """
    获取所有服务的配置（配置值自动 JSON 反序列化）
    
    Returns:
        配置字典 {service_name: {key: value}}
    """
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceConfigTbl)
            rows = list((await session.execute(stmt)).scalars().all())

    if not rows:
        return {}

    all_configs = {}
    for row in rows:
        if row.service_name not in all_configs:
            all_configs[row.service_name] = {}

        try:
            all_configs[row.service_name][row.conf_key] = orjson.loads(row.conf_value)
        except orjson.JSONDecodeError as e:
            logger.error(f"Failed to parse config {row.conf_key} for service {row.service_name}: {e}")
            all_configs[row.service_name][row.conf_key] = row.conf_value

    return all_configs

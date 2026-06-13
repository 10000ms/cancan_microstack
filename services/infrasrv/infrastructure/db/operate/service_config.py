from typing import List
import itertools

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import (
    select,
    update,
    delete,
    and_,
)

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_config import ServiceConfig
from cancan_microstack.services.infrasrv.infrastructure.db.model.service_config_tbl import ServiceConfigTbl


async def insert_service_config(confs: List[ServiceConfig]) -> None:
    async with Rmanager.pg_session() as session:
        batched_iter = itertools.batched(confs, 500)
        for chunk in batched_iter:
            async with session.begin():
                stmt = insert(ServiceConfigTbl).values(
                    [i.model_dump() for i in chunk]
                )
                # 冲突时更新字段
                stmt = stmt.on_conflict_do_update(
                    index_elements=["service_name", "conf_key"],
                    set_={
                        'conf_value': stmt.excluded.conf_value,
                    }
                )
                await session.execute(stmt)


async def get_service_config(service_name: str) -> List[ServiceConfig] | None:
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceConfigTbl).where(
                ServiceConfigTbl.service_name == service_name
            )
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceConfig.model_validate(r, from_attributes=True) for r in rows] if rows else None


async def update_service_config(confs: List[ServiceConfig]) -> None:
    async with Rmanager.pg_session() as session:
        async with session.begin():
            for conf in confs:
                stmt = update(ServiceConfigTbl).where(
                    and_(
                        ServiceConfigTbl.service_name == conf.service_name,
                        ServiceConfigTbl.conf_key == conf.conf_key,
                    )
                ).values(
                    conf_value=conf.conf_value,
                )
                await session.execute(stmt)
            return


async def get_all_service_configs() -> List[ServiceConfig]:
    """获取所有服务的配置"""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(ServiceConfigTbl)
            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceConfig.model_validate(r, from_attributes=True) for r in rows] if rows else []


async def delete_service_config(service_name: str, conf_key: str) -> None:
    """删除服务配置项"""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = delete(ServiceConfigTbl).where(
                and_(
                    ServiceConfigTbl.service_name == service_name,
                    ServiceConfigTbl.conf_key == conf_key,
                )
            )
            await session.execute(stmt)

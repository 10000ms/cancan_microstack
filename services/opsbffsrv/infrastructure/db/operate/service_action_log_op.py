"""
服务行为日志表数据库操作
"""
from typing import (
    List,
    Optional,
)
from sqlalchemy import select, desc

from linglong_web import Rmanager
from cancan_microstack.public.schemas.infra.service_action_log import ServiceActionLog
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.service_action_log_tbl import ServiceActionLogTbl


async def get_service_action_logs(
        service_name: Optional[str] = None,
        service_name_variants: Optional[List[str]] = None,
        action_type: Optional[str] = None,
        action_status: Optional[str] = None,
        limit: int = 100
) -> List[ServiceActionLog]:
    """
    查询服务行为日志
    
    Args:
        service_name: 服务名称（可选）
        action_type: 操作类型（可选）
        action_status: 操作状态（可选）
        limit: 返回数量限制
    
    Returns:
        服务行为日志列表
    """
    async with Rmanager.pg_session("infra") as session:
        async with session.begin():
            stmt = select(ServiceActionLogTbl).where(ServiceActionLogTbl.flag == 0)

            # 动态添加过滤条件
            candidates: List[str] = []
            if service_name_variants:
                candidates = sorted({name for name in service_name_variants if name})
            elif service_name:
                candidates = [service_name]

            if candidates:
                stmt = stmt.where(ServiceActionLogTbl.service_name.in_(candidates))
            if action_type:
                stmt = stmt.where(ServiceActionLogTbl.action_type == action_type)
            if action_status:
                stmt = stmt.where(ServiceActionLogTbl.action_status == action_status)

            # 按创建时间倒序排列
            stmt = stmt.order_by(desc(ServiceActionLogTbl.created_time))
            stmt = stmt.limit(limit)

            rows = list((await session.execute(stmt)).scalars().all())
            return [ServiceActionLog.model_validate(r, from_attributes=True) for r in rows] if rows else []

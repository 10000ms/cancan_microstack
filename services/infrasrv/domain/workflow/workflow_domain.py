"""
工作流领域服务
Workflow Domain Service

负责工作流的核心业务逻辑和规则验证，包括分布式锁保护的更新操作。
Handles workflow core business logic and rule validation, including update operations protected by distributed locks.
"""
import uuid
from typing import Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis

from cancan_microstack.public.const.redis import RedisKey
from cancan_microstack.public.error import HTTPException
from cancan_microstack.public.schemas.infra import workflow as wt
from linglong_web import Rmanager
from cancan_microstack.services.infrasrv.infrastructure.db.operate import workflow_op
from linglong_web.utils import logger


class WorkflowDomain:
    """
    工作流领域服务
    Workflow domain service for core business logic.
    """

    # Redis 锁的过期时间（秒）
    # Redis lock expiration time in seconds
    LOCK_EXPIRE_SECONDS = 60 * 5  # 5分钟

    def _get_workflow_lock(self, workflow_id: uuid.UUID):
        """
        基于 Redis 连接池创建分布式锁对象
        Create distributed lock object using Redis connection pool
        """
        if not Rmanager.RedisPool:
            raise HTTPException(status_code=500, msg="Redis pool is not initialized")

        redis_client = redis.Redis(connection_pool=Rmanager.RedisPool)
        lock_key = f"{RedisKey.WORKFLOW_UPDATE_PREFIX}{workflow_id}"
        return redis_client.lock(lock_key, timeout=self.LOCK_EXPIRE_SECONDS)

    @asynccontextmanager
    async def _acquire_workflow_lock(self, workflow_id: uuid.UUID):
        """
        获取工作流的分布式锁
        Acquire distributed lock for a workflow.

        Args:
            workflow_id: 工作流 ID / Workflow ID

        Yields:
            None

        Raises:
            HTTPException: 如果获取锁超时 / If lock acquisition times out
        """
        lock = self._get_workflow_lock(workflow_id)

        # blocking=True 结合 blocking_timeout 确保不会无限等待
        # blocking=True with blocking_timeout ensures we don't wait forever
        lock_acquired = await lock.acquire(blocking=True, blocking_timeout=self.LOCK_EXPIRE_SECONDS)

        if not lock_acquired:
            logger.warning(f"Failed to acquire lock for workflow {workflow_id}")
            raise HTTPException(
                status_code=409,
                msg=f"Workflow {workflow_id} is being modified by another process, please retry later"
            )

        try:
            logger.debug(f"Acquired lock for workflow {workflow_id}")
            yield
        finally:
            if lock.locked():
                await lock.release()
                logger.debug(f"Released lock for workflow {workflow_id}")

    async def update_workflow_definition(
            self,
            workflow_id: uuid.UUID,
            data: wt.WorkflowDefinitionUpdate
    ) -> Optional[wt.WorkflowDefinition]:
        """
        更新工作流定义（带分布式锁保护）
        Update workflow definition with distributed lock protection.

        Args:
            workflow_id: 工作流 ID / Workflow ID
            data: 更新数据 / Update data

        Returns:
            更新后的工作流定义，如果不存在则返回 None
            Updated workflow definition, or None if not found

        Raises:
            HTTPException: 如果无法获取锁 / If lock cannot be acquired
        """
        # 使用分布式锁保护更新操作
        # Protect update operation with distributed lock
        async with self._acquire_workflow_lock(workflow_id):
            logger.info(f"Updating workflow definition {workflow_id} with lock protection")

            # 调用基础设施层执行数据库更新
            # Call infrastructure layer to execute database update
            updated = await workflow_op.update_workflow_definition(workflow_id, data)

            if not updated:
                logger.warning(f"Workflow {workflow_id} not found during update")
                return None

            logger.info(f"Successfully updated workflow definition {workflow_id}")
            return updated

    async def rollback_workflow_definition(
            self,
            workflow_id: uuid.UUID,
            target_version: int,
            reason: Optional[str] = None,
    ) -> Optional[wt.WorkflowDefinition]:
        """
        回滚工作流定义（带分布式锁保护）
        Roll back workflow definition with distributed lock protection.

        Args:
            workflow_id: 工作流 ID / Workflow ID
            target_version: 目标版本号 / Target version number
            reason: 回滚原因 / Rollback reason

        Returns:
            回滚后的工作流定义 / Workflow definition after rollback
        """
        async with self._acquire_workflow_lock(workflow_id):
            logger.info(
                "Rolling back workflow %s to version %s with lock protection",
                workflow_id,
                target_version,
            )

            updated = await workflow_op.rollback_workflow_definition(
                workflow_id,
                target_version=target_version,
                reason=reason,
            )

            if not updated:
                logger.warning(
                    "Workflow %s rollback failed, version %s not found",
                    workflow_id,
                    target_version,
                )
                return None

            logger.info(
                "Workflow %s rolled back to version %s successfully",
                workflow_id,
                target_version,
            )
            return updated


# 全局实例 / Global instance
workflow_domain = WorkflowDomain()

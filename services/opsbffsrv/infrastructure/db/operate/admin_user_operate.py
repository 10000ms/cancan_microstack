"""admin_user_tbl 数据库操作 / DB operations for admin_user_tbl."""
from typing import Optional

from sqlalchemy import select, update

from linglong_web import Rmanager
from cancan_microstack.services.opsbffsrv.infrastructure.db.model.admin_user_tbl import AdminUserTbl


async def get_admin_user(username: str) -> Optional[AdminUserTbl]:
    """按用户名查询 admin 用户 / Get admin user by username."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(AdminUserTbl).where(
                AdminUserTbl.username == username,
                AdminUserTbl.flag == 0,
            )
            return (await session.execute(stmt)).scalar_one_or_none()


async def get_admin_user_by_id(user_id: int) -> Optional[AdminUserTbl]:
    """按 ID 查询 admin 用户 / Get admin user by ID."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = select(AdminUserTbl).where(
                AdminUserTbl.id == user_id,
                AdminUserTbl.flag == 0,
            )
            return (await session.execute(stmt)).scalar_one_or_none()


async def create_admin_user(username: str, password_hash: str) -> AdminUserTbl:
    """创建 admin 用户 / Create a new admin user."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            user = AdminUserTbl(username=username, password_hash=password_hash)
            session.add(user)
            await session.flush()
            return user


async def update_totp_secret(user_id: int, encrypted_secret: str) -> None:
    """更新 TOTP secret / Update encrypted TOTP secret for a user."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(AdminUserTbl).where(
                AdminUserTbl.id == user_id,
            ).values(totp_secret_encrypted=encrypted_secret)
            await session.execute(stmt)


async def mark_totp_bound(user_id: int) -> None:
    """标记 TOTP 已绑定 / Mark TOTP as bound for a user."""
    async with Rmanager.pg_session() as session:
        async with session.begin():
            stmt = update(AdminUserTbl).where(
                AdminUserTbl.id == user_id,
            ).values(totp_bound=True)
            await session.execute(stmt)

"""admin_user_tbl ORM 模型 / ORM model for admin_user_tbl."""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    SmallInteger,
    String,
    Text,
    TIMESTAMP,
)
from sqlalchemy.sql import func

from linglong_web import TableBase


class AdminUserTbl(TableBase):
    __tablename__ = "admin_user_tbl"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    totp_secret_encrypted = Column(Text, nullable=True)
    totp_bound = Column(Boolean, default=False)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return f"AdminUserTbl(id={self.id}, username={self.username})"

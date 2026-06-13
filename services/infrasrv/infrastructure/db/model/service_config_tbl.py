from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    SmallInteger,
    TIMESTAMP,
)
from sqlalchemy.sql import func

from linglong_web import TableBase


class ServiceConfigTbl(TableBase):
    __tablename__ = 'service_config_tbl'

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String, nullable=False)
    conf_key = Column(String, nullable=False)
    conf_value = Column(Text)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        {'extend_existing': True},
    )

    def __repr__(self):
        return f"ServiceConfigTbl(id={self.id}, service_name={self.service_name}, key={self.key})"

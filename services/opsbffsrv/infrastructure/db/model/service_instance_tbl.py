"""Service instance ORM for opsbff read-only queries."""
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Integer,
    Text,
    SmallInteger,
    TIMESTAMP,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from linglong_web import TableBase


class ServiceInstanceTbl(TableBase):
    """服务实例表 ORM (opsbff 只读)

    Mirrors the structure defined in infra to allow analytics on instance state.
    """

    __tablename__ = 'service_instance_tbl'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    service_name = Column(String(100), nullable=False)
    instance_id = Column(String(64), nullable=False, unique=True)
    container_name = Column(String(100), nullable=True)
    compose_service_name = Column(String(100), nullable=True)
    host = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    internal_port = Column(Integer, nullable=False, default=8080)
    status = Column(String(20), nullable=False, default='UP')
    expected_status = Column(String(20), default='UP')
    health_check_url = Column(String(255))
    health_status = Column(String(20), default='unknown')
    last_health_check = Column(TIMESTAMP(timezone=True))
    last_heartbeat = Column(TIMESTAMP(timezone=True))
    consecutive_failures = Column(SmallInteger, default=0)
    last_health_error = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True))
    stopped_at = Column(TIMESTAMP(timezone=True))
    restart_count = Column(Integer, default=0)
    cpu_limit = Column(String(20))
    memory_limit = Column(String(20))
    instance_metadata = Column(JSONB, default=dict)
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(
        TIMESTAMP(timezone=True),
        default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        Index('idx_service_instance_tbl_service_instance', 'service_name', 'instance_id'),
        Index('idx_service_instance_tbl_status', 'service_name', 'status'),
        Index('idx_service_instance_tbl_health_status', 'service_name', 'health_status'),
        Index('idx_service_instance_tbl_last_heartbeat', 'service_name', 'last_heartbeat'),
        {'extend_existing': True},
    )

    def __repr__(self) -> str:
        return (
            f"ServiceInstanceTbl(id={self.id}, service={self.service_name}, "
            f"instance={self.instance_id}, status={self.status})"
        )

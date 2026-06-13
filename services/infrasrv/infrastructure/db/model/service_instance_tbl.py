"""
服务实例表 ORM 模型
"""
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
    """
    服务实例表
    
    管理单服务的多实例信息，支持服务扩缩容。
    每个实例独立管理生命周期、健康检查和资源配置。
    """
    __tablename__ = 'service_instance_tbl'
    
    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 服务标识
    service_name = Column(String(100), nullable=False)          # 服务名称 (如 besrv)
    instance_id = Column(String(64), nullable=False, unique=True)  # 实例ID (如 besrv-0)
    
    # 容器配置
    container_name = Column(String(100), nullable=True, unique=True)  # Docker容器名
    compose_service_name = Column(String(100), nullable=True)  # Docker Compose服务名
    
    # 网络配置
    host = Column(String(100), nullable=False)  # 宿主机地址
    port = Column(Integer, nullable=False)      # 服务端口 (动态分配)
    internal_port = Column(Integer, nullable=False, default=8080)  # 容器内部端口
    
    # 健康检查配置（移至实例级）
    health_check_url = Column(String(255))
    
    # 实例状态
    status = Column(String(20), nullable=False, default='UP') # UP, DOWN, STARTING, etc.
    expected_status = Column(String(20), nullable=False, default='UP')  # running|stopped
    
    # 健康检查状态
    health_status = Column(String(20), default='unknown') # healthy|unhealthy|unknown
    last_health_check = Column(TIMESTAMP(timezone=True))  # 最后主动健康检查时间
    last_heartbeat = Column(TIMESTAMP(timezone=True))     # 最后心跳时间
    consecutive_failures = Column(SmallInteger, default=0)  # 连续失败次数
    last_health_error = Column(Text)                      # 最后一次健康检查错误
    
    # 生命周期
    started_at = Column(TIMESTAMP(timezone=True))   # 实例启动时间
    stopped_at = Column(TIMESTAMP(timezone=True))   # 实例停止时间
    restart_count = Column(Integer, default=0)      # 重启次数统计
    
    # 资源配置
    cpu_limit = Column(String(20))     # CPU限制
    memory_limit = Column(String(20))  # 内存限制
    
    # 元数据（直接使用 instance_metadata 字段名，不使用 alias）
    instance_metadata = Column(JSONB, default=dict)  # 实例元数据
    
    # 标准字段
    flag = Column(SmallInteger, default=0)
    created_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp())
    update_time = Column(TIMESTAMP(timezone=True), default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    __table_args__ = (
        Index('idx_service_instance_tbl_service_instance', 'service_name', 'instance_id'),
        Index('idx_service_instance_tbl_status', 'service_name', 'status'),
        Index('idx_service_instance_tbl_health_status', 'service_name', 'health_status'),
        Index('idx_service_instance_tbl_last_heartbeat', 'service_name', 'last_heartbeat'),
        {'extend_existing': True},
    )
    
    def __repr__(self):
        return (
            f"ServiceInstanceTbl(id={self.id}, instance_id={self.instance_id}, "
            f"service={self.service_name}, status={self.status}, "
            f"health={self.health_status}, port={self.port})"
        )

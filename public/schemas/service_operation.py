from enum import StrEnum


class OperationType(StrEnum):
    """服务操作类型"""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    # SCALE 仅作记录/占位用途，扩缩容动作未实现：
    # infrasrv 只记录 desired/actual 副本数（见 internal_update_service_replicas_handler），
    # controllersrv 没有 scale 执行能力，不会真正增减容器。
    SCALE = "scale"


class InitiatedFrom(StrEnum):
    """操作发起来源"""
    FRONTEND = "frontend"
    SYSTEM = "system"


class InitiatedBy(StrEnum):
    """操作发起者"""
    OPSBFFSRV = "opsbffsrv"
    INFRASRV = "infrasrv"

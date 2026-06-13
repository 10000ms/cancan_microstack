"""
服务行为日志相关的 Pydantic 类型定义
"""
from typing import (
    Optional,
    Dict,
    Any,
)
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ServiceActionLog(BaseModel):
    """服务行为日志数据模型"""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    service_name: str = Field(..., description="服务名称")
    instance_id: Optional[str] = Field(default=None, description="实例ID")
    action_type: str = Field(..., description="行为类型")
    action_status: str = Field(..., description="行为状态")
    action_detail: Optional[Dict[str, Any]] = Field(default=None, description="行为详情")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    triggered_by: str = Field(default="system", description="触发者")
    action_metadata: Optional[Dict[str, Any]] = Field(default=None, description="行为附加元数据")
    flag: int = Field(default=0, description="标志位")
    created_time: Optional[datetime] = None
    update_time: Optional[datetime] = None



class ServiceActionLogCreate(BaseModel):
    """创建服务行为日志的请求模型"""
    service_name: str = Field(..., description="服务名称")
    instance_id: Optional[str] = Field(default=None, description="实例ID")
    action_type: str = Field(..., description="行为类型：register, deregister, heartbeat, health_check_fail, restart, scale, rebuild")
    action_status: str = Field(..., description="行为状态：success, failed, in_progress")
    action_detail: Optional[Dict[str, Any]] = Field(default=None, description="行为详情")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    triggered_by: str = Field(default="system", description="触发者：system, user, auto")
    action_metadata: Optional[Dict[str, Any]] = Field(default=None, description="行为附加元数据")

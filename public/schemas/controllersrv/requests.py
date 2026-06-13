"""
controllersrv API 请求模型

定义了 controllersrv API 的请求模型，以确保一致性和类型安全。
"""
from typing import (
    Optional,
    List,
    Dict,
    Any,
)
from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class ServiceOperationRequest(BaseModel):
    """服务操作请求模型"""
    serial_number: str = Field(..., description="流水号，用于防重", min_length=1)
    service_names: List[str] = Field(..., description="服务名称列表", min_length=1)
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外参数")

    @field_validator('service_names')
    @classmethod
    def validate_service_names(cls, v):
        """验证服务名称列表"""
        if not v:
            raise ValueError("service_names must not be empty")
        for name in v:
            if not name or not isinstance(name, str) or not name.strip():
                raise ValueError(f"Invalid service name: {name}")
        return v

    @field_validator('serial_number')
    @classmethod
    def validate_serial_number(cls, v):
        """验证流水号并去除首尾空格"""
        if not v or not v.strip():
            raise ValueError("serial_number must not be empty")
        return v.strip()


class TaskQueryRequest(BaseModel):
    """任务查询请求模型"""
    serial_number: Optional[str] = Field(None, description="流水号")
    status: Optional[str] = Field(None, description="任务状态过滤")
    limit: int = Field(100, description="最大返回数量", ge=1, le=1000)


class ServiceStatusRequest(BaseModel):
    """服务状态查询请求模型"""
    service_names: Optional[List[str]] = Field(None, description="服务名称列表")
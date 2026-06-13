"""
Docker 操作相关的 API 响应模型
"""
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pydantic import BaseModel


class ContainerInfo(BaseModel):
    """容器基本信息"""
    id: str
    name: str
    status: str
    image: Any
    created: Optional[str] = None
    ports: Any
    labels: Dict[str, str]


class ContainerListResponse(BaseModel):
    """容器列表响应"""
    success: bool
    containers: Optional[List[ContainerInfo]] = None
    error: Optional[str] = None


class ContainerDetailResponse(BaseModel):
    """容器详情响应"""
    success: bool
    container: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ContainerLogsResponse(BaseModel):
    """容器日志响应"""
    success: bool
    logs: Optional[Any] = None
    error: Optional[str] = None


class ImageInfo(BaseModel):
    """镜像基本信息"""
    id: str
    tags: List[str]
    size: int
    created: Optional[str] = None


class ImageListResponse(BaseModel):
    """镜像列表响应"""
    success: bool
    images: Optional[List[ImageInfo]] = None
    error: Optional[str] = None


class NetworkInfo(BaseModel):
    """网络基本信息"""
    id: str
    name: str
    driver: str
    scope: str
    containers: List[Any]


class NetworkListResponse(BaseModel):
    """网络列表响应"""
    success: bool
    networks: Optional[List[NetworkInfo]] = None
    error: Optional[str] = None


class VolumeInfo(BaseModel):
    """卷基本信息"""
    name: str
    driver: str
    mountpoint: str


class VolumeListResponse(BaseModel):
    """卷列表响应"""
    success: bool
    volumes: Optional[List[VolumeInfo]] = None
    error: Optional[str] = None


class EngineInfo(BaseModel):
    """引擎信息"""
    version: str
    api_version: str
    os_type: str
    architecture: str


class EngineHealthResponse(BaseModel):
    """引擎健康状态响应"""
    success: bool
    healthy: Optional[bool] = None
    engine_info: Optional[EngineInfo] = None
    error: Optional[str] = None

"""
数据库初始化相关的类型定义
"""
from typing import (
    List,
    Optional,
    Dict,
    Any,
)

from pydantic import (
    BaseModel,
    Field,
)


class DatabaseInitRequest(BaseModel):
    """数据库初始化请求"""
    force: bool = Field(default=False, description="是否强制重建数据库（会删除已有数据）")
    databases: Optional[List[str]] = Field(default=None, description="要初始化的数据库列表，None 表示全部")


class DatabaseIncrementalBuildRequest(BaseModel):
    """数据库增量构建请求"""
    databases: Optional[List[str]] = Field(default=None, description="要增量构建的数据库列表，None 表示全部")
    tables: Optional[List[str]] = Field(default=None, description="要增量构建的表列表，None 表示全部")


class DatabaseBuildResult(BaseModel):
    """数据库构建结果"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="构建信息")
    databases_created: List[str] = Field(default_factory=list, description="新创建的数据库")
    tables_created: List[str] = Field(default_factory=list, description="新创建的表")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误信息列表")


class DatabaseInfo(BaseModel):
    """数据库信息"""
    name: str = Field(..., description="数据库名称")
    exists: bool = Field(..., description="是否存在")
    tables: List[str] = Field(default_factory=list, description="表列表")


class DatabaseStatus(BaseModel):
    """数据库状态"""
    databases: List[DatabaseInfo] = Field(default_factory=list, description="数据库列表")
    ddl_path: str = Field(..., description="DDL 文件路径")

"""
数据库初始化 API
提供数据库初始化和增量构建的 HTTP 接口
"""
from linglong_web import build_success_response
from linglong_web.utils import logger

from cancan_microstack.public.schemas.common import APIResponse
from cancan_microstack.public.schemas.opsbffsrv.db_init import (
    DatabaseInitRequest,
    DatabaseIncrementalBuildRequest,
    DatabaseBuildResult,
    DatabaseStatus,
)
from cancan_microstack.services.opsbffsrv.application.db_init_app import DatabaseInitApp

# 应用层实例（懒加载）
_db_init_app = None


def _get_app():
    """获取应用层实例"""
    global _db_init_app
    if _db_init_app is None:
        _db_init_app = DatabaseInitApp()
    return _db_init_app


async def initialize_databases_handler(
        request: DatabaseInitRequest,
) -> APIResponse[DatabaseBuildResult]:
    """
    一键初始化所有数据库
    
    POST /v1/opsbffsrv/db_init/initialize
    
    Body:
    {
        "force": false,  // 是否强制重建（会删除已有数据）
        "databases": ["infra", "ops", "biz"]  // 可选，不传则初始化全部
    }
    
    适用场景：
    - 首次部署，需要创建所有数据库和表
    - 测试环境重置
    """
    logger.info(f"Initialize databases request: {request}")
    app = _get_app()
    result = await app.initialize_all_databases(request)

    return build_success_response(data=result)


async def incremental_build_handler(
        request: DatabaseIncrementalBuildRequest,
) -> APIResponse[DatabaseBuildResult]:
    """
    增量构建数据库和表
    
    POST /v1/opsbffsrv/db_init/incremental
    
    Body:
    {
        "databases": ["infra", "ops"],  // 可选，不传则处理全部数据库
        "tables": ["service_config_tbl"]  // 可选，不传则处理全部表
    }
    
    逻辑：
    - 数据库不存在则创建，存在则跳过
    - 表不存在则创建，存在则跳过
    
    适用场景：
    - 新增数据库或表
    - 修复缺失的数据库/表
    - 开发环境同步
    """
    logger.info(f"Incremental build request: {request}")
    app = _get_app()
    result = await app.incremental_build(request)

    return build_success_response(data=result)


async def get_database_status_handler() -> APIResponse[DatabaseStatus]:
    """
    获取数据库状态
    
    GET /v1/opsbffsrv/db_init/status
    
    返回：
    {
        "success": true,
        "data": {
            "databases": [
                {
                    "name": "infra",
                    "exists": true,
                    "tables": ["service_config_tbl", "service_info_tbl", ...]
                },
                ...
            ],
            "ddl_path": "/path/to/ddl"
        }
    }
    """
    app = _get_app()
    status = await app.get_database_status()

    return build_success_response(data=status)

"""数据库初始化应用层 / DB init application layer.

负责数据库初始化和增量构建的业务流程编排。
Orchestrates database initialization and incremental builds.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from linglong_web.utils import logger
from linglong_web import Rmanager
from linglong_web import LinglongConfig

from cancan_microstack.services.opsbffsrv.domain.db_init.db_init_domain import DatabaseInitDomain
from cancan_microstack.public.schemas.opsbffsrv.db_init import (
    DatabaseInitRequest,
    DatabaseIncrementalBuildRequest,
    DatabaseBuildResult,
    DatabaseStatus,
    DatabaseInfo,
)


class DatabaseInitApp:
    """数据库初始化应用服务"""

    def __init__(self):
        self.domain = DatabaseInitDomain()

    async def initialize_all_databases(self, request: DatabaseInitRequest) -> DatabaseBuildResult:
        """
        一键初始化所有数据库（适用于首次部署）
        
        Args:
            request: 初始化请求
            
        Returns:
            构建结果
        """
        logger.info(f"Starting database initialization, force={request.force}")

        databases_to_init = request.databases or self.domain.get_all_databases()

        databases_created = []
        tables_created = []
        errors = []

        main_engine = None
        try:
            # 使用 main 数据库的连接来创建其他数据库
            # Create a temporary connection to the bootstrap DB (usually 'postgres' or 'main')
            #
            # 关键点：这是一次性管理操作，不应持久化连接池，否则多次调用会导致连接数持续上涨。
            # Key point: this is a one-off admin operation; do NOT keep a long-lived pool here.
            main_engine = create_async_engine(
                f"postgresql+asyncpg://{LinglongConfig.PGSQL_USER}:{LinglongConfig.PGSQL_PASSWORD}@{LinglongConfig.PGSQL_HOST}:{LinglongConfig.PGSQL_PORT}/main",
                poolclass=NullPool,
                pool_pre_ping=True,
                isolation_level="AUTOCOMMIT",  # 创建数据库需要在 AUTOCOMMIT 模式 / CREATE DATABASE needs AUTOCOMMIT
            )

            async with main_engine.connect() as conn:
                for db_name in databases_to_init:
                    logger.info(f"Processing database: {db_name}")

                    # 检查数据库是否存在
                    exists = await self.domain.check_database_exists(db_name, conn)

                    if exists and not request.force:
                        logger.info(f"Database '{db_name}' already exists, skipping creation")
                    elif exists and request.force:
                        # 强制模式：删除并重建
                        # 注意：DROP DATABASE 必须在 autocommit 模式下执行
                        logger.warning(f"Force mode: dropping database '{db_name}'")
                        try:
                            # 需要退出当前事务，使用 autocommit
                            await conn.execute(text(f"DROP DATABASE {db_name}"))
                            logger.info(f"Database '{db_name}' dropped")
                        except Exception as e:
                            logger.error(f"Failed to drop database '{db_name}': {e}", exc_info=True)
                            errors.append({
                                "database": db_name,
                                "operation": "drop",
                                "error": str(e)
                            })
                            continue

                    # 创建数据库（如果不存在或已删除）
                    if not exists or request.force:
                        if await self.domain.create_database(db_name, conn):
                            databases_created.append(db_name)
                            logger.info(f"Database '{db_name}' created")
                        else:
                            errors.append({
                                "database": db_name,
                                "operation": "create",
                                "error": "Failed to create database"
                            })
                            continue

                    # 需要先注册该数据库的引擎才能继续创建表
                    # 这里假设已经在配置中预先配置好了
                    # 如果没有配置，需要动态添加引擎注册

                    # 创建表（增量方式）
                    created, failed = await self.domain.create_tables_incremental(db_name)
                    tables_created.extend([f"{db_name}.{table}" for table in created])

                    if failed:
                        for table in failed:
                            errors.append({
                                "database": db_name,
                                "table": table,
                                "operation": "create_table",
                                "error": "Failed to create table"
                            })

            success = len(errors) == 0
            message = f"Initialized {len(databases_created)} databases, created {len(tables_created)} tables"
            if errors:
                message += f", {len(errors)} errors"

            return DatabaseBuildResult(
                success=success,
                message=message,
                databases_created=databases_created,
                tables_created=tables_created,
                errors=errors
            )

        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            return DatabaseBuildResult(
                success=False,
                message=f"Initialization failed: {str(e)}",
                databases_created=databases_created,
                tables_created=tables_created,
                errors=errors + [{"error": str(e)}]
            )

        finally:
            if main_engine is not None:
                try:
                    await main_engine.dispose()
                except Exception as dispose_exc:  # pragma: no cover - defensive cleanup
                    logger.warning("Failed to dispose main_engine: %s", dispose_exc)

    async def incremental_build(self, request: DatabaseIncrementalBuildRequest) -> DatabaseBuildResult:
        """
        增量构建数据库和表
        - 数据库不存在则创建，存在则跳过
        - 表不存在则创建，存在则跳过
        
        Args:
            request: 增量构建请求
            
        Returns:
            构建结果
        """
        logger.info(f"Starting incremental database build")

        databases_to_build = request.databases or self.domain.get_all_databases()

        databases_created = []
        tables_created = []
        errors = []

        try:
            # 使用 postgres 数据库的连接来创建其他数据库
            engine = Rmanager.get_pgsql_engine("default")
            if engine is None:
                return DatabaseBuildResult(
                    success=False,
                    message="Failed to get database connection",
                    databases_created=[],
                    tables_created=[],
                    errors=[{"error": "No default database engine available"}]
                )

            async with engine.connect() as conn:
                for db_name in databases_to_build:
                    logger.info(f"Processing database: {db_name}")

                    # 检查数据库是否存在
                    exists = await self.domain.check_database_exists(db_name, conn)

                    # 数据库不存在则创建
                    if not exists:
                        if await self.domain.create_database(db_name, conn):
                            databases_created.append(db_name)
                            logger.info(f"Database '{db_name}' created")
                        else:
                            errors.append({
                                "database": db_name,
                                "operation": "create",
                                "error": "Failed to create database"
                            })
                            continue
                    else:
                        logger.info(f"Database '{db_name}' already exists")

                    # 增量创建表
                    created, failed = await self.domain.create_tables_incremental(
                        db_name,
                        request.tables
                    )
                    tables_created.extend([f"{db_name}.{table}" for table in created])

                    if failed:
                        for table in failed:
                            errors.append({
                                "database": db_name,
                                "table": table,
                                "operation": "create_table",
                                "error": "Failed to create table"
                            })

            success = len(errors) == 0
            message = f"Built {len(databases_created)} new databases, created {len(tables_created)} tables"
            if errors:
                message += f", {len(errors)} errors"

            return DatabaseBuildResult(
                success=success,
                message=message,
                databases_created=databases_created,
                tables_created=tables_created,
                errors=errors
            )

        except Exception as e:
            logger.error(f"Incremental build failed: {e}", exc_info=True)
            return DatabaseBuildResult(
                success=False,
                message=f"Build failed: {str(e)}",
                databases_created=databases_created,
                tables_created=tables_created,
                errors=errors + [{"error": str(e)}]
            )

    async def get_database_status(self) -> DatabaseStatus:
        """
        获取数据库状态
        
        Returns:
            数据库状态信息
        """
        databases = []

        try:
            engine = Rmanager.get_pgsql_engine("default")
            if engine is None:
                return DatabaseStatus(
                    databases=[],
                    ddl_path=str(self.domain.ddl_root)
                )

            async with engine.connect() as conn:
                for db_name in self.domain.get_all_databases():
                    exists = await self.domain.check_database_exists(db_name, conn)

                    tables = []
                    if exists:
                        tables = list(await self.domain.get_existing_tables(db_name))

                    databases.append(DatabaseInfo(
                        name=db_name,
                        exists=exists,
                        tables=tables
                    ))

            return DatabaseStatus(
                databases=databases,
                ddl_path=str(self.domain.ddl_root)
            )

        except Exception as e:
            logger.error(f"Failed to get database status: {e}", exc_info=True)
            return DatabaseStatus(
                databases=[],
                ddl_path=str(self.domain.ddl_root)
            )

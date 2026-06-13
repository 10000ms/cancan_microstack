"""
数据库初始化领域层
负责数据库和表的创建、检查等核心业务逻辑
"""
from pathlib import Path
from typing import (
    List,
    Optional,
    Set,
    Tuple,
)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from linglong_web.utils import logger
from linglong_web import Rmanager
from linglong_web import LinglongConfig

from cancan_microstack.runtime.resources import resolve_workspace_or_asset


class DatabaseInitDomain:
    """数据库初始化领域服务"""

    # 数据库和对应的 DDL 目录映射
    DB_DDL_MAPPING = {
        "infra": "infra",
        "ops": "ops",
        "biz": "biz",
    }

    def __init__(self, ddl_root_path: str = None):
        """
        初始化
        
        Args:
            ddl_root_path: DDL 文件根目录，默认为项目根目录/ddl
        """
        if ddl_root_path is None:
            ddl_root = resolve_workspace_or_asset("ddl", "ddl")
        else:
            ddl_root = Path(ddl_root_path)

        self.ddl_root = ddl_root
        logger.info(f"DatabaseInitDomain initialized with DDL path: {self.ddl_root}")

    async def check_database_exists(self, database_name: str, conn: AsyncConnection) -> bool:
        """
        检查数据库是否存在
        
        Args:
            database_name: 数据库名称
            conn: 数据库连接
            
        Returns:
            数据库是否存在
        """
        query = text("SELECT 1 FROM pg_database WHERE datname = :dbname")
        result = await conn.execute(query, {"dbname": database_name})
        return result.scalar() is not None

    async def create_database(self, database_name: str, conn: AsyncConnection) -> bool:
        """
        创建数据库
        
        Args:
            database_name: 数据库名称
            conn: 数据库连接（必须是 postgres 或其他存在的数据库）
            
        Returns:
            是否成功创建
        """
        try:
            # 必须在自动提交模式下创建数据库
            await conn.execute(text("COMMIT"))
            await conn.execute(text(f"CREATE DATABASE {database_name}"))
            logger.info(f"Database '{database_name}' created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create database '{database_name}': {e}")
            return False

    async def get_existing_tables(self, database_name: str) -> Set[str]:
        """
        获取数据库中已存在的表
        
        Args:
            database_name: 数据库名称
            
        Returns:
            表名集合
        """
        try:
            # 尝试使用指定数据库的引擎，如果没有则创建临时连接
            engine = Rmanager.get_pgsql_engine(database_name)
            if engine is None:
                # 没有预注册的引擎，需要临时连接
                # 临时引擎必须避免连接池残留，否则高频调用会推高 Postgres 连接数。
                # Temporary engine must avoid pooled connections; otherwise frequent calls can exhaust Postgres.
                temp_engine = create_async_engine(
                    f"postgresql+asyncpg://{LinglongConfig.PGSQL_USER}:{LinglongConfig.PGSQL_PASSWORD}@{LinglongConfig.PGSQL_HOST}:{LinglongConfig.PGSQL_PORT}/{database_name}",
                    poolclass=NullPool,
                    pool_pre_ping=True,
                )

                try:
                    async with temp_engine.begin() as conn:
                        query = text("""
                            SELECT tablename 
                            FROM pg_tables 
                            WHERE schemaname = 'public'
                        """)
                        result = await conn.execute(query)
                        tables = {row[0] for row in result}
                finally:
                    await temp_engine.dispose()

                return tables

            async with engine.begin() as conn:
                query = text("""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
                result = await conn.execute(query)
                return {row[0] for row in result}
        except Exception as e:
            logger.error(f"Failed to get tables for database '{database_name}': {e}")
            return set()

    def get_sql_files_for_database(self, database_name: str) -> List[Tuple[str, str]]:
        """
        获取数据库对应的 SQL 文件列表
        
        Args:
            database_name: 数据库名称
            
        Returns:
            (表名, SQL文件路径) 的列表
        """
        ddl_dir = self.DB_DDL_MAPPING.get(database_name)
        if not ddl_dir:
            logger.warning(f"No DDL directory mapping for database '{database_name}'")
            return []

        sql_dir = self.ddl_root / ddl_dir
        if not sql_dir.exists():
            logger.warning(f"DDL directory not found: {sql_dir}")
            return []

        sql_files = []
        for sql_file in sorted(sql_dir.glob("*.sql")):
            # 表名就是文件名（去掉 .sql 后缀）
            table_name = sql_file.stem
            sql_files.append((table_name, str(sql_file)))

        return sql_files

    async def execute_sql_file(self, sql_file_path: str, database_name: str) -> bool:
        """
        执行 SQL 文件（支持多条语句）
        
        Args:
            sql_file_path: SQL 文件路径
            database_name: 目标数据库名称
            
        Returns:
            是否成功执行
        """
        try:
            # 读取 SQL 文件
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 拆分 SQL 语句（按分号分隔，忽略注释中的分号）
            statements = self._split_sql_statements(sql_content)

            # 尝试使用指定数据库的引擎，如果没有则创建临时连接
            engine = Rmanager.get_pgsql_engine(database_name)
            if engine is None:
                # 没有预注册的引擎，需要临时连接
                # 临时引擎必须避免连接池残留，否则高频调用会推高 Postgres 连接数。
                # Temporary engine must avoid pooled connections; otherwise frequent calls can exhaust Postgres.
                temp_engine = create_async_engine(
                    f"postgresql+asyncpg://{LinglongConfig.PGSQL_USER}:{LinglongConfig.PGSQL_PASSWORD}@{LinglongConfig.PGSQL_HOST}:{LinglongConfig.PGSQL_PORT}/{database_name}",
                    poolclass=NullPool,
                    pool_pre_ping=True,
                )

                try:
                    async with temp_engine.begin() as conn:
                        # 逐条执行 SQL 语句
                        for stmt in statements:
                            if stmt.strip():  # 跳过空语句
                                await conn.execute(text(stmt))
                finally:
                    await temp_engine.dispose()
            else:
                async with engine.begin() as conn:
                    # 逐条执行 SQL 语句
                    for stmt in statements:
                        if stmt.strip():  # 跳过空语句
                            await conn.execute(text(stmt))

            logger.info(f"Executed SQL file: {sql_file_path} ({len(statements)} statements)")
            return True

        except Exception as e:
            logger.error(f"Failed to execute SQL file '{sql_file_path}': {e}", exc_info=True)
            return False

    def _split_sql_statements(self, sql_content: str) -> List[str]:
        """
        拆分 SQL 内容为多条语句
        
        处理规则：
        1. 按分号分隔
        2. 忽略 -- 注释
        3. 处理 $$ dollar-quoted 字符串（不拆分其中的分号）
        4. 处理 'string' 单引号字符串
        
        Args:
            sql_content: SQL 文件内容
            
        Returns:
            SQL 语句列表
        """
        statements = []
        current_statement = []
        in_dollar_quote = False
        in_single_quote = False

        for line in sql_content.split('\n'):
            # 跳过纯注释行
            stripped_line = line.strip()
            if stripped_line.startswith('--'):
                continue

            # 检查 dollar-quoted 字符串状态
            # 简单处理：如果行中包含 $$，切换状态
            dollar_count = line.count('$$')
            if dollar_count % 2 == 1:  # 奇数个 $$ 表示状态切换
                in_dollar_quote = not in_dollar_quote

            # 在 dollar-quoted 字符串内部，不检查分号
            if in_dollar_quote:
                current_statement.append(line)
                continue

            # 移除行尾注释（不在字符串内的注释）
            # 简化处理：如果不在引号内，可以移除注释
            line_without_comment = line.split('--')[0] if '--' in line else line

            # 检查是否包含分号（语句结束符）
            if ';' in line_without_comment:
                # 分号前的内容加入当前语句
                parts = line_without_comment.split(';')
                current_statement.append(parts[0])

                # 完成当前语句
                stmt = '\n'.join(current_statement).strip()
                if stmt and stmt not in ('BEGIN', 'COMMIT'):  # 跳过 BEGIN/COMMIT
                    statements.append(stmt)

                # 重置当前语句
                current_statement = []

                # 如果分号后还有内容，作为新语句的开始
                if parts[-1].strip():
                    current_statement.append(parts[-1])
            else:
                # 没有分号，继续累积
                current_statement.append(line)

        # 处理最后可能未结束的语句
        if current_statement:
            stmt = '\n'.join(current_statement).strip()
            if stmt and stmt not in ('BEGIN', 'COMMIT'):
                statements.append(stmt)

        return statements

    async def ensure_triggers_exist(self, database_name: str) -> bool:
        """
        确保数据库中存在必要的触发器函数
        
        Args:
            database_name: 数据库名称
            
        Returns:
            是否成功
        """
        trigger_file = self.ddl_root / "trigger.sql"
        if not trigger_file.exists():
            logger.warning(f"Trigger file not found: {trigger_file}")
            return True  # 文件不存在也不算失败，可能不需要触发器

        logger.info(f"Ensuring triggers exist in '{database_name}'...")
        return await self.execute_sql_file(str(trigger_file), database_name)

    async def create_tables_incremental(
            self,
            database_name: str,
            target_tables: Optional[List[str]] = None
    ) -> Tuple[List[str], List[str]]:
        """
        增量创建表（只创建不存在的表）
        
        Args:
            database_name: 数据库名称
            target_tables: 目标表列表，None 表示全部
            
        Returns:
            (成功创建的表列表, 失败的表列表)
        """
        # 首先确保触发器函数存在
        await self.ensure_triggers_exist(database_name)

        # 获取已存在的表
        existing_tables = await self.get_existing_tables(database_name)

        # 获取 SQL 文件列表
        sql_files = self.get_sql_files_for_database(database_name)

        created_tables = []
        failed_tables = []

        for table_name, sql_file in sql_files:
            # 如果指定了目标表，只处理目标表
            if target_tables and table_name not in target_tables:
                continue

            # 如果表已存在，跳过
            if table_name in existing_tables:
                logger.info(f"Table '{table_name}' already exists in '{database_name}', skipping")
                continue

            # 创建表
            logger.info(f"Creating table '{table_name}' in '{database_name}'...")
            if await self.execute_sql_file(sql_file, database_name):
                created_tables.append(table_name)
            else:
                failed_tables.append(table_name)

        return created_tables, failed_tables

    def get_all_databases(self) -> List[str]:
        """
        获取所有配置的数据库列表
        
        Returns:
            数据库名称列表
        """
        return list(self.DB_DDL_MAPPING.keys())

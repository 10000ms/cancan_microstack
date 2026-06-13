from typing import (
    List,
    Mapping,
    Optional,
)
from typing_extensions import Literal

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
)


class SchemaApplyRequest(BaseModel):
    """Request payload for ensuring canonical schema state."""

    databases: Optional[List[str]] = Field(default=None, description="Target database names; defaults to all")
    tables: Optional[List[str]] = Field(default=None, description="Optional subset of tables to process")
    dry_run: bool = Field(default=False, description="When true, report drift without applying changes")


class SchemaRebuildDatabaseRequest(BaseModel):
    """Request payload for rebuilding an entire database."""

    database: str = Field(..., description="Database name to rebuild")


class SchemaRebuildTablesRequest(BaseModel):
    """Request payload for rebuilding specific tables."""

    database: str = Field(..., description="Database containing the tables")
    tables: List[str] = Field(..., description="One or more table names to rebuild")
    cascade: bool = Field(default=True, description="Cascade when dropping tables (drops dependent objects)")


class SchemaDiffRequest(BaseModel):
    """Request payload for schema drift inspection."""

    databases: Optional[List[str]] = Field(default=None, description="Databases to inspect")
    tables: Optional[List[str]] = Field(default=None, description="Optional subset of tables to inspect")


class SchemaOperationSummary(BaseModel):
    """模式操作概要信息 / Summary produced by schema operations."""

    databases: int = Field(..., description="处理的数据库数量 / Number of databases processed")
    created_tables: int = Field(..., description="新建或重建的数据表数量 / Count of created or recreated tables")
    skipped_tables: int = Field(..., description="跳过的数据表数量 / Count of skipped tables")
    tables_with_drift: int = Field(..., description="存在偏差的数据表数量 / Count of tables with schema drift")


class SchemaColumnMismatch(BaseModel):
    """数据列差异细节 / Detailed description of a column mismatch."""

    model_config = ConfigDict(extra="ignore")

    column: str = Field(..., description="数据列名称 / Column name")
    expected_type: Optional[str] = Field(default=None, description="预期数据类型 / Expected data type")
    actual_type: Optional[str] = Field(default=None, description="实际数据类型 / Actual data type")
    expected_not_null: Optional[bool] = Field(default=None, description="预期非空约束 / Expected NOT NULL constraint")
    actual_not_null: Optional[bool] = Field(default=None, description="实际非空约束 / Actual NOT NULL constraint")
    expected_default: Optional[str] = Field(default=None, description="预期默认值 / Expected default value")
    actual_default: Optional[str] = Field(default=None, description="实际默认值 / Actual default value")


class SchemaColumnDiff(BaseModel):
    """数据列差异汇总 / Aggregated column difference summary."""

    missing_columns: List[str] = Field(default_factory=list, description="缺失列列表 / Missing column names")
    extra_columns: List[str] = Field(default_factory=list, description="多余列列表 / Extra column names")
    mismatched_columns: List[SchemaColumnMismatch] = Field(default_factory=list,
                                                           description="列差异详情 / Column mismatch details")


class SchemaTableDiff(BaseModel):
    """数据表差异信息 / Table-level diff information."""

    table_exists: bool = Field(..., description="数据表是否存在 / Whether the table exists")
    comment_hash_matches: bool = Field(..., description="注释 Hash 是否匹配 / Whether the comment hash matches")
    column_diff: SchemaColumnDiff = Field(..., description="列差异信息 / Column difference information")


class SchemaStatementReport(BaseModel):
    """单条 SQL 语句执行结果 / Execution report for a single SQL statement."""

    kind: str = Field(..., description="语句类型 / Statement kind")
    action: str = Field(..., description="执行动作 / Execution action")
    name: Optional[str] = Field(default=None, description="对象名称 / Optional object name")
    message: Optional[str] = Field(default=None, description="附加信息 / Optional execution message")


class SchemaTableResult(BaseModel):
    """数据表执行结果 / Result of applying canonical DDL to a table."""

    table: str = Field(..., description="数据表名称 / Table name")
    ddl_path: str = Field(..., description="DDL 文件路径 / DDL file path")
    hash: str = Field(..., description="DDL 文件 Hash / Hash of the DDL file")
    status: str = Field(..., description="执行状态 / Execution status")
    statements: List[SchemaStatementReport] = Field(..., description="语句执行报告 / Statement execution reports")
    diff: SchemaTableDiff = Field(..., description="数据表差异信息 / Table difference details")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表 / Warning messages")


class SchemaDatabaseResult(BaseModel):
    """数据库执行结果 / Result of schema operations for a database."""

    database: str = Field(..., description="数据库名称 / Database name")
    database_created: bool = Field(..., description="是否新创建数据库 / Whether the database was created")
    warnings: List[str] = Field(default_factory=list, description="数据库级警告 / Database level warnings")
    tables: List[SchemaTableResult] = Field(..., description="数据表执行结果列表 / Table results")


class SchemaOperationData(BaseModel):
    """模式操作核心数据 / Core payload returned by schema operations."""

    summary: SchemaOperationSummary = Field(..., description="概要信息 / Summary information")
    databases: List[SchemaDatabaseResult] = Field(..., description="数据库执行结果列表 / Database results")


class SchemaOperationCLIResult(BaseModel):
    """dbadmin CLI 返回结果封装 / Wrapper for dbadmin CLI payload."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["success"] = Field(..., description="执行状态 / Execution status")
    data: SchemaOperationData = Field(..., description="操作数据 / Operation data")
    warnings: Optional[List[str]] = Field(default=None, description="全局警告信息 / Optional global warnings")


class SchemaOperationResponse(BaseModel):
    """API 返回的模式操作结果 / Schema operation response returned to clients."""

    summary: SchemaOperationSummary = Field(..., description="概要信息 / Summary information")
    databases: List[SchemaDatabaseResult] = Field(..., description="数据库执行结果列表 / Database results")
    warnings: List[str] = Field(default_factory=list, description="全局警告信息 / Global warning messages")

    @classmethod
    def from_cli_payload(cls, payload: Mapping[str, object]) -> "SchemaOperationResponse":
        """从 CLI 原始数据构建响应 / Build response from raw CLI payload."""

        parsed = SchemaOperationCLIResult.model_validate(payload)
        return cls(
            summary=parsed.data.summary,
            databases=parsed.data.databases,
            warnings=parsed.warnings or [],
        )

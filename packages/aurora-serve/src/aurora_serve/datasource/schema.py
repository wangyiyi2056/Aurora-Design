from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


SUPPORTED_DB_TYPES = [
    "sqlite",
    "postgresql",
    "mysql",
    "duckdb",
    "clickhouse",
    "mssql",
    "oracle",
    "starrocks",
    "vertica",
    "hive",
]


class DBConfig(BaseModel):
    name: str = Field(..., description="Unique datasource name")
    db_type: str = Field(..., description="Database type identifier")
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    description: Optional[str] = Field("", description="Description of this datasource")
    extra: Dict[str, Any] = Field(default_factory=dict)


class ParameterDefinition(BaseModel):
    name: str
    label: str
    type: str = "string"
    required: bool = False
    default: Optional[Any] = None
    description: str = ""
    placeholder: str = ""


class DatasourceTypeInfo(BaseModel):
    name: str
    label: str
    description: str = ""
    icon: str = ""
    is_file_db: bool = False
    parameters: List[ParameterDefinition] = []


class DatasourceTypesResponse(BaseModel):
    types: List[DatasourceTypeInfo]


class DatasourceCreate(BaseModel):
    config: DBConfig


class DatasourceResponse(BaseModel):
    name: str
    db_type: str
    description: str = ""
    connected: bool = False
    tables: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class DatasourceListResponse(BaseModel):
    items: List[DatasourceResponse]


class SchemaResponse(BaseModel):
    name: str
    schema_ddl: str


class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    success: bool
    result: Any
    error: Optional[str] = None


class DatabaseSummaryResponse(BaseModel):
    name: str
    db_type: str
    tables: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)


# ── Saved Queries ─────────────────────────────────────────────────

class SavedQueryCreate(BaseModel):
    datasource_name: str = Field(..., description="Datasource this query belongs to")
    sql: str = Field(..., description="SQL statement")
    description: str = Field("", description="Human-readable label for this query")


class SavedQueryUpdate(BaseModel):
    sql: Optional[str] = Field(None, description="SQL statement")
    description: Optional[str] = Field(None, description="Human-readable label for this query")


class SavedQueryResponse(BaseModel):
    id: str
    datasource_name: str
    sql: str
    description: str = ""
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class SavedQueryListResponse(BaseModel):
    items: List[SavedQueryResponse]

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DBConfig(BaseModel):
    name: str = Field(..., description="Unique datasource name")
    db_type: str = Field(..., description="sqlite | postgresql | mysql | duckdb")
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class DatasourceCreate(BaseModel):
    config: DBConfig


class DatasourceResponse(BaseModel):
    name: str
    db_type: str
    connected: bool = False
    tables: Optional[List[str]] = None
    error: Optional[str] = None


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

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional, Tuple

from aurora_core.component import BaseService
from aurora_core.datasource.base import BaseConnector
from aurora_core.datasource.rdbms.clickhouse import ClickHouseConnector
from aurora_core.datasource.rdbms.duckdb import DuckDBConnector
from aurora_core.datasource.rdbms.hive import HiveConnector
from aurora_core.datasource.rdbms.mssql import MSSQLConnector
from aurora_core.datasource.rdbms.mysql import MySQLConnector
from aurora_core.datasource.rdbms.oracle import OracleConnector
from aurora_core.datasource.rdbms.postgresql import PostgreSQLConnector
from aurora_core.datasource.rdbms.sqlite import SQLiteConnector
from aurora_core.datasource.rdbms.starrocks import StarRocksConnector
from aurora_core.datasource.rdbms.vertica import VerticaConnector
from aurora_serve.datasource.schema import (
    DBConfig,
    DatasourceTypeInfo,
    DatasourceTypesResponse,
    ParameterDefinition,
    SUPPORTED_DB_TYPES,
)
from aurora_serve.metadata import DatasourceEntity, MetadataStore, SavedQueryEntity

logger = logging.getLogger(__name__)

_CONNECTOR_CACHE_TTL = 1800  # 30 minutes

_HOST_PARAM = ParameterDefinition(
    name="host", label="Host", required=True, default="localhost",
    description="Database host address", placeholder="localhost",
)
_PORT_PARAM = lambda default_port: ParameterDefinition(
    name="port", label="Port", type="number", required=True,
    default=default_port, description="Database port",
)
_USER_PARAM = lambda default_user: ParameterDefinition(
    name="user", label="User", required=True, default=default_user,
    description="Database username", placeholder=default_user,
)
_PWD_PARAM = ParameterDefinition(
    name="password", label="Password", type="password",
    description="Database password",
)
_DB_PARAM = lambda default_db: ParameterDefinition(
    name="database", label="Database", required=True, default=default_db,
    description="Database name", placeholder=default_db,
)
_DESC_PARAM = ParameterDefinition(
    name="description", label="Description",
    description="Description of this datasource",
)

_NETWORK_DB_PARAMS = lambda port, user, db: [
    _HOST_PARAM, _PORT_PARAM(port), _USER_PARAM(user), _PWD_PARAM, _DB_PARAM(db), _DESC_PARAM,
]

DB_TYPE_REGISTRY: Dict[str, DatasourceTypeInfo] = {
    "sqlite": DatasourceTypeInfo(
        name="sqlite", label="SQLite", icon="database",
        description="File-based embedded database", is_file_db=True,
        parameters=[
            ParameterDefinition(
                name="database", label="Database Path", required=True,
                default=":memory:", description="File path or :memory:",
                placeholder="/path/to/db.sqlite",
            ),
            _DESC_PARAM,
        ],
    ),
    "duckdb": DatasourceTypeInfo(
        name="duckdb", label="DuckDB", icon="database",
        description="Analytical embedded database", is_file_db=True,
        parameters=[
            ParameterDefinition(
                name="database", label="Database Path", required=True,
                default=":memory:", description="File path or :memory:",
                placeholder="/path/to/db.duckdb",
            ),
            _DESC_PARAM,
        ],
    ),
    "postgresql": DatasourceTypeInfo(
        name="postgresql", label="PostgreSQL", icon="database",
        description="Open-source relational database",
        parameters=_NETWORK_DB_PARAMS(5432, "postgres", "postgres"),
    ),
    "mysql": DatasourceTypeInfo(
        name="mysql", label="MySQL", icon="database",
        description="Popular open-source relational database",
        parameters=_NETWORK_DB_PARAMS(3306, "root", "mysql"),
    ),
    "clickhouse": DatasourceTypeInfo(
        name="clickhouse", label="ClickHouse", icon="bar-chart",
        description="Column-oriented analytics database",
        parameters=_NETWORK_DB_PARAMS(8123, "default", "default"),
    ),
    "mssql": DatasourceTypeInfo(
        name="mssql", label="SQL Server", icon="database",
        description="Microsoft SQL Server",
        parameters=_NETWORK_DB_PARAMS(1433, "sa", "master"),
    ),
    "oracle": DatasourceTypeInfo(
        name="oracle", label="Oracle", icon="database",
        description="Oracle Database",
        parameters=[
            _HOST_PARAM, _PORT_PARAM(1521), _USER_PARAM("system"), _PWD_PARAM,
            _DB_PARAM("ORCL"),
            ParameterDefinition(
                name="service_name", label="Service Name",
                description="Oracle service name (alternative to SID)",
            ),
            _DESC_PARAM,
        ],
    ),
    "starrocks": DatasourceTypeInfo(
        name="starrocks", label="StarRocks", icon="star",
        description="High-performance analytical database",
        parameters=_NETWORK_DB_PARAMS(9030, "root", "default"),
    ),
    "vertica": DatasourceTypeInfo(
        name="vertica", label="Vertica", icon="database",
        description="Columnar analytics platform",
        parameters=_NETWORK_DB_PARAMS(5433, "dbadmin", "VMart"),
    ),
    "hive": DatasourceTypeInfo(
        name="hive", label="Hive", icon="database",
        description="Data warehouse on Hadoop",
        parameters=_NETWORK_DB_PARAMS(10000, "hive", "default"),
    ),
}


class DatasourceService(BaseService):
    name = "datasource_service"

    def __init__(self, metadata_store: MetadataStore | None = None):
        self.metadata_store = metadata_store
        self._connectors: Dict[str, BaseConnector] = {}
        self._connector_cache: Dict[str, Tuple[float, BaseConnector]] = {}
        self._cache_lock = threading.Lock()
        if metadata_store is not None:
            self._load_saved_connections()

    # ── CRUD ────────────────────────────────────────────────────────

    def add_connection(self, config: DBConfig) -> None:
        connector = self._build_connector(config)
        with self._cache_lock:
            self._connector_cache[config.name] = (time.time(), connector)
        self._connectors[config.name] = connector
        if self.metadata_store is not None:
            with self.metadata_store.session() as session:
                entity = session.get(DatasourceEntity, config.name)
                if entity is None:
                    entity = DatasourceEntity(name=config.name, db_type=config.db_type)
                    session.add(entity)
                entity.db_type = config.db_type
                entity.host = config.host
                entity.port = config.port
                entity.user = config.user
                entity.password = config.password
                entity.database = config.database
                entity.description = config.description or ""
                entity.extra = config.extra
                session.commit()

    def remove_connection(self, name: str) -> bool:
        removed = False
        self._invalidate_cache(name)
        if name in self._connectors:
            del self._connectors[name]
            removed = True
        if self.metadata_store is not None:
            with self.metadata_store.session() as session:
                entity = session.get(DatasourceEntity, name)
                if entity is not None:
                    session.delete(entity)
                    session.commit()
                    removed = True
        return removed

    def get_connector(self, name: str) -> BaseConnector:
        now = time.time()
        with self._cache_lock:
            cached = self._connector_cache.get(name)
            if cached and now - cached[0] < _CONNECTOR_CACHE_TTL:
                return cached[1]
        if name not in self._connectors:
            raise KeyError(f"Datasource '{name}' not found")
        connector = self._connectors[name]
        with self._cache_lock:
            self._connector_cache[name] = (time.time(), connector)
        return connector

    def get_config(self, name: str) -> DBConfig:
        if self.metadata_store is not None:
            with self.metadata_store.session() as session:
                entity = session.get(DatasourceEntity, name)
                if entity is None:
                    raise KeyError(f"Datasource '{name}' not found")
                return DBConfig(
                    name=entity.name,
                    db_type=entity.db_type,
                    host=entity.host,
                    port=entity.port,
                    user=entity.user,
                    password=entity.password,
                    database=entity.database,
                    description=entity.description,
                    extra=entity.extra or {},
                )
        connector = self.get_connector(name)
        return DBConfig(name=name, db_type=connector.db_type)

    def get_entity(self, name: str) -> Optional[DatasourceEntity]:
        if self.metadata_store is None:
            return None
        with self.metadata_store.session() as session:
            return session.get(DatasourceEntity, name)

    def list_connections(self) -> List[str]:
        return list(self._connectors.keys())

    def list_all(self) -> List[dict]:
        if self.metadata_store is None:
            return [{"name": n, "db_type": c.db_type} for n, c in self._connectors.items()]
        with self.metadata_store.session() as session:
            entities = session.query(DatasourceEntity).all()
            return [
                {
                    "name": e.name,
                    "db_type": e.db_type,
                    "description": e.description or "",
                    "created_at": e.created_at,
                    "updated_at": e.updated_at,
                }
                for e in entities
            ]

    # ── Test / Refresh ──────────────────────────────────────────────

    def test_connection(self, config: DBConfig) -> tuple[bool, Optional[str]]:
        try:
            connector = self._build_connector(config)
            connector.get_table_names()
            return True, None
        except Exception as e:
            return False, str(e)

    def refresh(self, name: str) -> bool:
        self._invalidate_cache(name)
        if self.metadata_store is not None:
            config = self.get_config(name)
            connector = self._build_connector(config)
            self._connectors[name] = connector
            with self._cache_lock:
                self._connector_cache[name] = (time.time(), connector)
            return True
        return name in self._connectors

    # ── Supported Types ─────────────────────────────────────────────

    def get_supported_types(self) -> DatasourceTypesResponse:
        types = [DB_TYPE_REGISTRY[t] for t in SUPPORTED_DB_TYPES if t in DB_TYPE_REGISTRY]
        return DatasourceTypesResponse(types=types)

    # ── Database Summary ────────────────────────────────────────────

    def get_database_summary(self, name: str) -> dict:
        connector = self.get_connector(name)
        if hasattr(connector, "get_database_summary"):
            return connector.get_database_summary()
        tables = connector.get_table_names()
        return {"db_type": connector.db_type, "tables": {t: {} for t in tables}, "relationships": []}

    # ── Saved Queries ───────────────────────────────────────────────

    def list_saved_queries(self, datasource_name: str) -> List[dict]:
        if self.metadata_store is None:
            return []
        with self.metadata_store.session() as session:
            entities = (
                session.query(SavedQueryEntity)
                .filter(SavedQueryEntity.datasource_name == datasource_name)
                .order_by(SavedQueryEntity.created_at.desc())
                .all()
            )
            return [
                {
                    "id": e.id,
                    "datasource_name": e.datasource_name,
                    "sql": e.sql,
                    "description": e.description,
                    "created_at": e.created_at,
                    "updated_at": e.updated_at,
                }
                for e in entities
            ]

    def save_query(self, datasource_name: str, sql: str, description: str) -> dict:
        if self.metadata_store is None:
            raise RuntimeError("Metadata store not available")
        entity = SavedQueryEntity(
            id=uuid.uuid4().hex,
            datasource_name=datasource_name,
            sql=sql,
            description=description,
        )
        with self.metadata_store.session() as session:
            session.add(entity)
            session.commit()
        return {
            "id": entity.id,
            "datasource_name": entity.datasource_name,
            "sql": entity.sql,
            "description": entity.description,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        }

    def update_saved_query(self, query_id: str, sql: str | None = None, description: str | None = None) -> dict | None:
        if self.metadata_store is None:
            return None
        with self.metadata_store.session() as session:
            entity = session.get(SavedQueryEntity, query_id)
            if entity is None:
                return None
            if sql is not None:
                entity.sql = sql
            if description is not None:
                entity.description = description
            session.commit()
            return {
                "id": entity.id,
                "datasource_name": entity.datasource_name,
                "sql": entity.sql,
                "description": entity.description,
                "created_at": entity.created_at,
                "updated_at": entity.updated_at,
            }

    def delete_saved_query(self, query_id: str) -> bool:
        if self.metadata_store is None:
            return False
        with self.metadata_store.session() as session:
            entity = session.get(SavedQueryEntity, query_id)
            if entity is None:
                return False
            session.delete(entity)
            session.commit()
            return True

    # ── Cache ───────────────────────────────────────────────────────

    def _invalidate_cache(self, name: str) -> None:
        with self._cache_lock:
            entry = self._connector_cache.pop(name, None)
        if entry is not None:
            _, connector = entry
            engine = getattr(connector, "_engine", None)
            if engine and hasattr(engine, "dispose"):
                try:
                    engine.dispose()
                except Exception:
                    pass

    # ── Build Connector ─────────────────────────────────────────────

    def _build_connector(self, config: DBConfig) -> BaseConnector:
        db_type = config.db_type.lower()
        extra = config.extra or {}

        if db_type == "sqlite":
            return SQLiteConnector(database=config.database or ":memory:")
        if db_type == "duckdb":
            return DuckDBConnector(database=config.database or ":memory:")
        if db_type == "postgresql":
            return PostgreSQLConnector(
                host=config.host or "localhost",
                port=config.port or 5432,
                user=config.user or "postgres",
                password=config.password or "",
                database=config.database or "postgres",
            )
        if db_type == "mysql":
            return MySQLConnector(
                host=config.host or "localhost",
                port=config.port or 3306,
                user=config.user or "root",
                password=config.password or "",
                database=config.database or "mysql",
            )
        if db_type == "clickhouse":
            return ClickHouseConnector(
                host=config.host or "localhost",
                port=config.port or 8123,
                user=config.user or "default",
                password=config.password or "",
                database=config.database or "default",
            )
        if db_type == "mssql":
            return MSSQLConnector(
                host=config.host or "localhost",
                port=config.port or 1433,
                user=config.user or "sa",
                password=config.password or "",
                database=config.database or "master",
            )
        if db_type == "oracle":
            return OracleConnector(
                host=config.host or "localhost",
                port=config.port or 1521,
                user=config.user or "system",
                password=config.password or "",
                database=config.database or "ORCL",
                service_name=extra.get("service_name", ""),
            )
        if db_type == "starrocks":
            return StarRocksConnector(
                host=config.host or "localhost",
                port=config.port or 9030,
                user=config.user or "root",
                password=config.password or "",
                database=config.database or "default",
            )
        if db_type == "vertica":
            return VerticaConnector(
                host=config.host or "localhost",
                port=config.port or 5433,
                user=config.user or "dbadmin",
                password=config.password or "",
                database=config.database or "VMart",
            )
        if db_type == "hive":
            return HiveConnector(
                host=config.host or "localhost",
                port=config.port or 10000,
                user=config.user or "hive",
                password=config.password or "",
                database=config.database or "default",
            )
        raise ValueError(f"Unsupported db_type: {db_type}")

    def _load_saved_connections(self) -> None:
        with self.metadata_store.session() as session:
            for entity in session.query(DatasourceEntity).all():
                config = DBConfig(
                    name=entity.name,
                    db_type=entity.db_type,
                    host=entity.host,
                    port=entity.port,
                    user=entity.user,
                    password=entity.password,
                    database=entity.database,
                    description=entity.description if hasattr(entity, "description") else "",
                    extra=entity.extra or {},
                )
                try:
                    self._connectors[entity.name] = self._build_connector(config)
                except Exception:
                    logger.warning("Failed to load datasource %s", entity.name)

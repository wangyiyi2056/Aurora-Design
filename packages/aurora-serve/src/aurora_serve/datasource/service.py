from typing import Dict, List, Optional

from aurora_core.component import BaseService
from aurora_core.datasource.base import BaseConnector
from aurora_core.datasource.rdbms.duckdb import DuckDBConnector
from aurora_core.datasource.rdbms.mysql import MySQLConnector
from aurora_core.datasource.rdbms.postgresql import PostgreSQLConnector
from aurora_core.datasource.rdbms.sqlite import SQLiteConnector
from aurora_serve.datasource.schema import DBConfig
from aurora_serve.metadata import DatasourceEntity, MetadataStore


class DatasourceService(BaseService):
    name = "datasource_service"

    def __init__(self, metadata_store: MetadataStore | None = None):
        self.metadata_store = metadata_store
        self._connectors: Dict[str, BaseConnector] = {}
        if metadata_store is not None:
            self._load_saved_connections()

    def add_connection(self, config: DBConfig) -> None:
        connector = self._build_connector(config)
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
                entity.extra = config.extra
                session.commit()

    def remove_connection(self, name: str) -> bool:
        removed = False
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
        if name not in self._connectors:
            raise KeyError(f"Datasource '{name}' not found")
        return self._connectors[name]

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
                    extra=entity.extra or {},
                )
        connector = self.get_connector(name)
        return DBConfig(name=name, db_type=connector.db_type)

    def list_connections(self) -> List[str]:
        return list(self._connectors.keys())

    def test_connection(self, config: DBConfig) -> tuple[bool, Optional[str]]:
        try:
            connector = self._build_connector(config)
            connector.get_table_names()
            return True, None
        except Exception as e:
            return False, str(e)

    def _build_connector(self, config: DBConfig) -> BaseConnector:
        db_type = config.db_type.lower()
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
                    extra=entity.extra or {},
                )
                self._connectors[entity.name] = self._build_connector(config)

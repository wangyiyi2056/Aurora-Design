from typing import Dict, List, Optional

from chatbi_core.datasource.base import BaseConnector
from chatbi_core.datasource.rdbms.duckdb import DuckDBConnector
from chatbi_core.datasource.rdbms.mysql import MySQLConnector
from chatbi_core.datasource.rdbms.postgresql import PostgreSQLConnector
from chatbi_core.datasource.rdbms.sqlite import SQLiteConnector
from chatbi_serve.datasource.schema import DBConfig


class DatasourceService:
    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}

    def add_connection(self, config: DBConfig) -> None:
        connector = self._build_connector(config)
        self._connectors[config.name] = connector

    def remove_connection(self, name: str) -> bool:
        if name in self._connectors:
            del self._connectors[name]
            return True
        return False

    def get_connector(self, name: str) -> BaseConnector:
        if name not in self._connectors:
            raise KeyError(f"Datasource '{name}' not found")
        return self._connectors[name]

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

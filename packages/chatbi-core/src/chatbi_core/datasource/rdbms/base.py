from typing import Dict, List, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from chatbi_core.datasource.base import BaseConnector


class RDBMSConnector(BaseConnector):
    def __init__(self, connection_string: str, db_type: str):
        self._db_type = db_type
        self._engine: Engine = create_engine(connection_string)

    @property
    def db_type(self) -> str:
        return self._db_type

    def get_table_names(self) -> List[str]:
        inspector = inspect(self._engine)
        return inspector.get_table_names()

    def get_table_schema(self, table: str) -> str:
        inspector = inspect(self._engine)
        columns = inspector.get_columns(table)
        lines = [f"CREATE TABLE {table} ("]
        col_defs = []
        for col in columns:
            col_type = str(col["type"])
            nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
            col_defs.append(f"  {col['name']} {col_type} {nullable}")
        lines.append(",\n".join(col_defs))
        lines.append(")")
        return "\n".join(lines)

    def get_table_schemas(self, tables: List[str] | None = None) -> str:
        if tables is None:
            tables = self.get_table_names()
        schemas = []
        for table in tables:
            try:
                schemas.append(self.get_table_schema(table))
            except Exception:
                continue
        return "\n\n".join(schemas)

    def query(self, sql: str) -> List[Dict]:
        with self._engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    def run(self, sql: str) -> Tuple[bool, str]:
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(sql))
                if result.returns_rows:
                    rows = result.mappings().all()
                    data = [dict(row) for row in rows]
                    return True, str(data)
                conn.commit()
                return True, f"Affected rows: {result.rowcount}"
        except Exception as e:
            return False, str(e)

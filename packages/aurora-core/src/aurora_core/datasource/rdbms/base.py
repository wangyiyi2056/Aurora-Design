from typing import Dict, List, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from aurora_core.datasource.base import BaseConnector


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

    def get_table_indexes(self, table: str) -> List[Dict]:
        """Get index information for a table."""
        inspector = inspect(self._engine)
        indexes = inspector.get_indexes(table)
        result = []
        for idx in indexes:
            result.append({
                "name": idx.get("name", ""),
                "columns": idx.get("column_names", []),
                "unique": idx.get("unique", False),
            })
        return result

    def get_table_foreign_keys(self, table: str) -> List[Dict]:
        """Get foreign key information for a table."""
        inspector = inspect(self._engine)
        fks = inspector.get_foreign_keys(table)
        result = []
        for fk in fks:
            result.append({
                "name": fk.get("name", ""),
                "constrained_columns": fk.get("constrained_columns", []),
                "referred_table": fk.get("referred_table", ""),
                "referred_columns": fk.get("referred_columns", []),
            })
        return result

    def get_table_primary_keys(self, table: str) -> List[str]:
        """Get primary key columns for a table."""
        inspector = inspect(self._engine)
        pk = inspector.get_pk_constraint(table)
        return pk.get("constrained_columns", [])

    def get_table_row_count(self, table: str) -> int:
        """Get approximate row count for a table."""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                return result.scalar() or 0
        except Exception:
            return -1

    def get_database_summary(self, tables: List[str] | None = None) -> Dict:
        """Get comprehensive database summary including relationships."""
        if tables is None:
            tables = self.get_table_names()

        summary = {
            "db_type": self._db_type,
            "tables": {},
            "relationships": [],
        }

        for table in tables:
            try:
                columns = inspect(self._engine).get_columns(table)
                indexes = self.get_table_indexes(table)
                fks = self.get_table_foreign_keys(table)
                pk = self.get_table_primary_keys(table)
                row_count = self.get_table_row_count(table)

                summary["tables"][table] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                            "primary_key": col["name"] in pk,
                        }
                        for col in columns
                    ],
                    "indexes": indexes,
                    "foreign_keys": fks,
                    "primary_key": pk,
                    "row_count": row_count,
                }

                for fk in fks:
                    if fk.get("referred_table"):
                        summary["relationships"].append({
                            "from_table": table,
                            "from_columns": fk.get("constrained_columns", []),
                            "to_table": fk.get("referred_table", ""),
                            "to_columns": fk.get("referred_columns", []),
                            "name": fk.get("name", ""),
                        })
            except Exception:
                continue

        return summary

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

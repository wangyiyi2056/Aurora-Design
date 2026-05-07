import json
from typing import Any, Optional

from aurora_core.agent.skill.base import BaseSkill
from aurora_serve.datasource.service import DatasourceService


class DatabaseSummarySkill(BaseSkill):
    """Retrieve comprehensive database summary including table relationships, indexes, foreign keys, and statistics."""

    def __init__(
        self,
        datasource_service: Optional[DatasourceService] = None,
        datasource_name: str = "",
    ):
        self._datasource = datasource_service
        self._datasource_name = datasource_name

    @property
    def name(self) -> str:
        return "database_summary"

    @property
    def description(self) -> str:
        return (
            "Get a comprehensive database summary including table schemas, indexes, "
            "foreign keys, primary keys, row counts, and table relationships. "
            "Use this for understanding the full database structure and data relationships."
        )

    @property
    def description_cn(self) -> str:
        return "获取数据库完整摘要，包括表结构、索引、外键、主键、行数和表关系。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of table names to summarize. If empty, all tables are included.",
                },
                "include_row_counts": {
                    "type": "boolean",
                    "description": "Whether to include row count estimates (default true).",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        tables: list[str] | None = None,
        include_row_counts: bool = True,
        **kwargs: Any,
    ) -> str:
        if not self._datasource:
            return "Datasource service not available."

        ds_name = kwargs.get("datasource_name") or self._datasource_name
        if not ds_name:
            return "No datasource selected."

        try:
            connector = self._datasource.get_connector(ds_name)
        except Exception as e:
            return f"Datasource error: {e}"

        try:
            # Get the database summary using the enhanced connector methods
            if hasattr(connector, "get_database_summary"):
                summary = connector.get_database_summary(tables)
            else:
                # Fallback for connectors without the enhanced methods
                if tables is None:
                    tables = connector.get_table_names()

                summary = {
                    "db_type": connector.db_type,
                    "tables": {},
                    "relationships": [],
                }

                for table in tables:
                    schema = connector.get_table_schema(table)
                    summary["tables"][table] = {
                        "schema": schema,
                        "columns": [],
                        "indexes": [],
                        "foreign_keys": [],
                        "primary_key": [],
                        "row_count": -1,
                    }

            # Build text summary
            lines = [
                f"Database Summary ({summary['db_type']})",
                "=" * 50,
                f"Tables: {len(summary['tables'])}",
                f"Relationships: {len(summary['relationships'])}",
                "",
            ]

            for table_name, table_info in summary["tables"].items():
                lines.append(f"Table: {table_name}")
                lines.append("-" * 40)

                if table_info.get("row_count", -1) >= 0 and include_row_counts:
                    lines.append(f"  Row Count: {table_info['row_count']}")

                pk = table_info.get("primary_key", [])
                if pk:
                    lines.append(f"  Primary Key: {pk}")

                columns = table_info.get("columns", [])
                if columns:
                    lines.append("  Columns:")
                    for col in columns:
                        pk_marker = " [PK]" if col.get("primary_key") else ""
                        nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                        lines.append(
                            f"    - {col['name']}: {col['type']} {nullable}{pk_marker}"
                        )

                indexes = table_info.get("indexes", [])
                if indexes:
                    lines.append("  Indexes:")
                    for idx in indexes:
                        unique_marker = " [UNIQUE]" if idx.get("unique") else ""
                        lines.append(
                            f"    - {idx.get('name', 'unnamed')}: {idx.get('columns', [])}{unique_marker}"
                        )

                fks = table_info.get("foreign_keys", [])
                if fks:
                    lines.append("  Foreign Keys:")
                    for fk in fks:
                        lines.append(
                            f"    - {fk.get('name', 'unnamed')}: "
                            f"{fk.get('constrained_columns', [])} -> "
                            f"{fk.get('referred_table', '')}.{fk.get('referred_columns', [])}"
                        )

                lines.append("")

            if summary["relationships"]:
                lines.append("Table Relationships:")
                lines.append("-" * 40)
                for rel in summary["relationships"]:
                    lines.append(
                        f"  {rel['from_table']}.{rel['from_columns']} -> "
                        f"{rel['to_table']}.{rel['to_columns']}"
                    )

            lines.append("")
            lines.append("Raw JSON Summary:")
            lines.append(json.dumps(summary, ensure_ascii=False, indent=2))

            return "\n".join(lines)
        except Exception as e:
            return f"Error retrieving database summary: {e}"
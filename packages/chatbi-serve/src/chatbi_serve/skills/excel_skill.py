import csv
import json
import re
from pathlib import Path
from typing import Any, Optional

from chatbi_core.agent.skill.base import BaseSkill
from chatbi_serve.datasource.service import DatasourceService


def _infer_sql_type(value: Any) -> str:
    """Infer SQL column type from a sample value."""
    if value is None or value == "":
        return "TEXT"
    try:
        int(str(value))
        return "INTEGER"
    except ValueError:
        pass
    try:
        float(str(value))
        return "REAL"
    except ValueError:
        pass
    return "TEXT"


def _sanitize_column_name(name: str) -> str:
    """Sanitize column name for SQL."""
    s = re.sub(r"[^\w\u4e00-\u9fff]", "_", str(name))
    if s[0].isdigit():
        s = "_" + s
    return s or "col"


def _read_csv_data(file_path: str) -> tuple[list[str], list[dict[str, Any]]]:
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = [_sanitize_column_name(h) for h in reader.fieldnames or []]
        rows = []
        for row in reader:
            rows.append({_sanitize_column_name(k): v for k, v in row.items()})
    return headers, rows


def _read_excel_data(file_path: str) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError("pandas is required to read Excel files") from e

    df = pd.read_excel(file_path, engine="openpyxl", keep_default_na=False)
    headers = [_sanitize_column_name(str(h)) for h in df.columns]
    rows = []
    for _, row in df.iterrows():
        rows.append({h: row.iloc[i] for i, h in enumerate(headers)})
    return headers, rows


def _read_tabular_data(file_path: str) -> tuple[list[str], list[dict[str, Any]]]:
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        return _read_csv_data(file_path)
    if ext in (".xlsx", ".xls"):
        return _read_excel_data(file_path)
    raise ValueError(f"Unsupported file format: {ext}. Only .csv and .xlsx are supported.")


class Excel2TableSkill(BaseSkill):
    """Import a CSV or Excel file into the database as a new table."""

    def __init__(
        self,
        datasource_service: Optional[DatasourceService] = None,
        datasource_name: str = "",
    ):
        self._datasource = datasource_service
        self._datasource_name = datasource_name

    @property
    def name(self) -> str:
        return "excel2table"

    @property
    def description(self) -> str:
        return (
            "Import a CSV or Excel (.xlsx) file into the database as a new table. "
            "The file must already be uploaded and the local file_path must be provided."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local path to the uploaded CSV or Excel file.",
                },
                "table_name": {
                    "type": "string",
                    "description": "Name of the database table to create. If empty, derived from the filename.",
                },
            },
            "required": ["file_path"],
        }

    async def execute(
        self, file_path: str = "", table_name: str = "", **kwargs: Any
    ) -> str:
        if not file_path:
            return "No file_path provided."
        if not Path(file_path).exists():
            return f"File not found: {file_path}"
        if not self._datasource:
            return "Datasource service not available."

        ds_name = kwargs.get("datasource_name") or self._datasource_name
        if not ds_name:
            return "No datasource selected."

        try:
            connector = self._datasource.get_connector(ds_name)
        except Exception as e:
            return f"Datasource error: {e}"

        if not table_name:
            table_name = _sanitize_column_name(Path(file_path).stem)

        try:
            headers, rows = _read_tabular_data(file_path)
        except Exception as e:
            return f"Failed to read file: {e}"

        if not headers:
            return "No columns found in the file."

        # Infer types from first few rows
        type_map: dict[str, str] = {}
        for header in headers:
            col_type = "TEXT"
            for row in rows[:100]:
                inferred = _infer_sql_type(row.get(header))
                if inferred == "REAL":
                    col_type = "REAL"
                elif inferred == "INTEGER" and col_type not in ("REAL",):
                    col_type = "INTEGER"
                if col_type == "REAL":
                    break
            type_map[header] = col_type

        # Build CREATE TABLE
        col_defs = [f'"{h}" {type_map[h]}' for h in headers]
        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({', '.join(col_defs)});'

        # Execute CREATE TABLE
        success, result = connector.run(create_sql)
        if not success:
            return f"Failed to create table: {result}\n\nSQL: {create_sql}"

        # Build INSERT SQL in batches
        batch_size = 500
        total_inserted = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            placeholders = ", ".join([f"({', '.join(['?' for _ in headers])})" for _ in batch])
            # Use parameterized style compatible with most engines via text()
            # But our connector.run() doesn't support params, so we do value escaping
            values_clauses = []
            for row in batch:
                vals = []
                for h in headers:
                    v = row.get(h)
                    if v is None or v == "":
                        vals.append("NULL")
                    else:
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                values_clauses.append(f"({', '.join(vals)})")

            insert_sql = (
                f'INSERT INTO "{table_name}" ({', '.join([f'"{h}"' for h in headers])}) '
                f'VALUES {', '.join(values_clauses)};'
            )
            success, result = connector.run(insert_sql)
            if not success:
                return f"Failed to insert data: {result}\n\nSQL: {insert_sql[:200]}..."
            total_inserted += len(batch)

        return (
            f"Successfully imported '{Path(file_path).name}' into table '{table_name}'.\n"
            f"Columns: {headers}\n"
            f"Rows inserted: {total_inserted}"
        )

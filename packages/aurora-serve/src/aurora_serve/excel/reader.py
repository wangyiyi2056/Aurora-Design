"""ExcelReader — DuckDB native connection, file import, SQL execution, table transform.

Uses DuckDB's native Python API directly (not SQLAlchemy) for maximum performance
with native read_csv / read_xlsx / read_json_auto / read_parquet.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

import duckdb

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

logger = logging.getLogger(__name__)

_SQL_COMMENT_RE = re.compile(r"--[^\n]*|/\*[\s\S]*?\*/")
_IDENT_RE = re.compile(r"[^0-9a-zA-Z_]+")
_DUCKDB_RESERVED = {
    "select",
    "from",
    "where",
    "group",
    "order",
    "by",
    "table",
    "create",
    "drop",
    "delete",
    "insert",
    "update",
    "with",
    "as",
    "join",
}

_ZH_COLUMN_TERMS = {
    "类别": "category",
    "分类": "category",
    "品类": "category",
    "销售额": "sales_amount",
    "销售金额": "sales_amount",
    "金额": "amount",
    "利润": "profit",
    "地区": "region",
    "日期": "date",
    "时间": "time",
    "数量": "quantity",
    "订单": "order",
    "客户": "customer",
}


@dataclass
class TransformedExcelResponse:
    description: str
    columns: list[dict[str, str]]
    plans: list[str]


def _import_via_pandas(
    db: DuckDBPyConnection,
    file_path: str,
    file_name: str,
    table_name: str,
) -> str:
    """Fallback import for .xls (legacy format) using pandas."""
    import numpy as np
    import pandas as pd

    if file_name.endswith((".xls", ".xlsx")):
        df = pd.read_excel(file_path, index_col=False)
    elif file_name.endswith(".csv"):
        # Detect encoding for non-UTF-8 CSV files
        try:
            import chardet
            with open(file_path, "rb") as f:
                raw = f.read(10000)
            detected = chardet.detect(raw)
            encoding = detected.get("encoding", "utf-8-sig")
        except ImportError:
            encoding = "utf-8-sig"
        df = pd.read_csv(file_path, index_col=False, encoding=encoding)
    else:
        raise ValueError(f"Unsupported file format for pandas import: {file_name}")

    df = df.replace("", np.nan)
    # Drop fully-unnamed columns
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed") and df[c].isnull().all()]
    df = df.drop(columns=unnamed)

    # Sanitize column names
    df = df.rename(columns=lambda x: str(x).strip().replace(" ", "_"))
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            try:
                df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                df[col] = df[col].astype(str)

    db.register("temp_df_table", df)
    db.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM temp_df_table')
    return table_name


def quote_identifier(identifier: str) -> str:
    """Quote a DuckDB identifier safely."""
    return '"' + identifier.replace('"', '""') + '"'


def sanitize_identifier(value: str, fallback: str) -> str:
    """Normalize an LLM-provided column/table identifier into safe DuckDB SQL."""
    raw = str(value or "").strip()
    lowered = raw.lower()
    for zh, english in _ZH_COLUMN_TERMS.items():
        lowered = lowered.replace(zh, english)
    lowered = lowered.replace("%", " percent ")
    lowered = _IDENT_RE.sub("_", lowered.lower()).strip("_")
    lowered = re.sub(r"_+", "_", lowered)
    if not lowered:
        lowered = fallback
    if lowered[0].isdigit():
        lowered = f"col_{lowered}"
    if lowered in _DUCKDB_RESERVED:
        lowered = f"{lowered}_col"
    return lowered


def sanitize_column_mapping(columns: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return a copy of column mappings with unique safe new_column_name values."""
    used: dict[str, int] = {}
    sanitized: list[dict[str, str]] = []
    for index, column in enumerate(columns, start=1):
        base = sanitize_identifier(
            str(column.get("new_column_name") or column.get("old_column_name") or ""),
            fallback=f"column_{index}",
        )
        count = used.get(base, 0) + 1
        used[base] = count
        safe_name = base if count == 1 else f"{base}_{count}"
        sanitized.append({**column, "new_column_name": safe_name})
    return sanitized


def ensure_read_only_sql(sql: str) -> str:
    """Validate and normalize SQL allowed for Excel analysis."""
    cleaned = _SQL_COMMENT_RE.sub("", sql or "").strip()
    if ";" in cleaned.rstrip(";"):
        raise ValueError("Only read-only SQL is allowed for Excel analysis.")
    cleaned = cleaned.rstrip(";").strip()
    if not cleaned:
        raise ValueError("Only read-only SQL is allowed for Excel analysis.")
    first = re.match(r"^\s*([a-zA-Z]+)", cleaned)
    keyword = first.group(1).lower() if first else ""
    if keyword not in {"select", "with", "summarize", "describe"}:
        raise ValueError("Only read-only SQL is allowed for Excel analysis.")
    return cleaned


class ExcelReader:
    """DuckDB-native Excel/CSV reader and query executor."""

    def __init__(
        self,
        file_path: str,
        file_name: Optional[str] = None,
        database: str = ":memory:",
        table_name: str = "data_analysis_table",
    ):
        if not file_name:
            file_name = os.path.basename(file_path)

        db_exists = os.path.exists(database) and database != ":memory:"

        self.db: DuckDBPyConnection = duckdb.connect(database=database, read_only=False)
        self.file_path = file_path
        self.file_name = file_name
        self.temp_table = "temp_table"
        self.table_name = table_name

        if not db_exists:
            self.import_file()
        # else: db already persisted with data

    # ── file import ────────────────────────────────────────────

    def import_file(self) -> str:
        """Import file into DuckDB using native readers. Falls back to pandas for .xls."""
        ext = os.path.splitext(self.file_path)[1].lower()
        temp = self.temp_table
        if self._table_exists(temp):
            return temp

        try:
            # Try automatic detection first
            self.db.sql(f"CREATE TABLE {quote_identifier(temp)} AS SELECT * FROM '{self.file_path}'")
            return temp
        except Exception:
            logger.debug("Auto-detection failed, trying explicit reader")

        load_params: dict[str, str] = {}
        if ext == ".csv":
            load_func = "read_csv"
        elif ext == ".xlsx":
            load_func = "read_xlsx"
            load_params["empty_as_varchar"] = "true"
            load_params["ignore_errors"] = "true"
        elif ext == ".json":
            load_func = "read_json_auto"
        elif ext == ".parquet":
            load_func = "read_parquet"
        elif ext == ".xls":
            return _import_via_pandas(self.db, self.file_path, self.file_name, temp)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        func_args = ", ".join(f"{k}={v}" for k, v in load_params.items())
        from_exp = (
            f"FROM {load_func}('{self.file_path}', {func_args})"
            if func_args
            else f"FROM {load_func}('{self.file_path}')"
        )
        try:
            self.db.sql(f"CREATE TABLE {quote_identifier(temp)} AS SELECT * {from_exp}")
        except Exception:
            return _import_via_pandas(self.db, self.file_path, self.file_name, temp)

        return temp

    def _table_exists(self, table_name: str) -> bool:
        result = self.db.sql(
            "SELECT COUNT(*) FROM duckdb_tables() WHERE schema_name='main' AND table_name=?",
            params=[table_name],
        )
        return bool(result.fetchone()[0])

    # ── SQL execution ──────────────────────────────────────────

    def run_sql(self, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Execute SQL, return (column_names, rows)."""
        sql = ensure_read_only_sql(sql)
        logger.info(f"Executing SQL: {sql[:500]}")
        try:
            result = self.db.sql(sql)
            cols = [desc[0] for desc in result.description]
            return cols, result.fetchall()
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            raise ValueError(f"Data query error!\nSQL: {sql[:300]}\nError: {e}") from e

    def run_sql_df(self, sql: str):
        """Execute SQL, return pandas DataFrame."""
        sql = ensure_read_only_sql(sql)
        return self.db.sql(sql).df()

    # ── metadata queries ───────────────────────────────────────

    def get_sample_data(self, table_name: Optional[str] = None) -> tuple[list[str], list[tuple[Any, ...]]]:
        tn = table_name or self.table_name
        return self.run_sql(f"SELECT * FROM {tn} USING SAMPLE 5;")

    def get_columns(self, table_name: Optional[str] = None) -> tuple[list[str], list[tuple[Any, ...]]]:
        tn = table_name or self.table_name
        sql = f"""
            SELECT
                dc.column_name,
                dc.data_type AS column_type,
                CASE WHEN dc.is_nullable THEN 'YES' ELSE 'NO' END AS nullable,
                '' AS key,
                '' AS default_val,
                '' AS extra,
                dc.comment
            FROM duckdb_columns() dc
            WHERE dc.table_name = '{tn}'
              AND dc.schema_name = 'main';
        """
        return self.run_sql(sql)

    def get_create_table_sql(self, table_name: Optional[str] = None) -> str:
        tn = table_name or self.table_name
        sql = f"""
            SELECT comment, table_name, database_name
            FROM duckdb_tables()
            WHERE table_name = '{tn}'
        """
        _, datas = self.run_sql(sql)
        table_comment = datas[0][0] if datas else ""
        _, cl_datas = self.get_columns(tn)

        lines = [f"CREATE TABLE {tn} ("]
        col_strs = []
        for row in cl_datas:
            col_name, col_type, nullable, key, default_val, _extra, comment = row
            s = f"    {col_name} {col_type}"
            if key == "PRI":
                s += " PRIMARY KEY"
            elif nullable and str(nullable).upper() == "NO":
                s += " NOT NULL"
            if default_val:
                s += f" DEFAULT {default_val}"
            col_strs.append(s)
        lines.append(",\n".join(col_strs))
        if table_comment:
            lines.append(f"\n) COMMENT '{table_comment}';")
        else:
            lines.append("\n);")
        return "\n".join(lines)

    def get_summary(self, table_name: Optional[str] = None) -> str:
        tn = table_name or self.table_name
        df = self.db.sql(f"SUMMARIZE {tn}").df()
        return df.to_json(orient="records", force_ascii=False)

    # ── table transformation ───────────────────────────────────

    def transform_table(
        self,
        old_table: str,
        new_table: str,
        transform: TransformedExcelResponse,
    ) -> str:
        """Create new_table with standardized column names and comments."""
        _, cl_datas = self.get_columns(old_table)
        old_col_types = {row[0]: row[1] for row in cl_datas}
        safe_columns = sanitize_column_mapping(transform.columns)

        select_parts: list[str] = []
        create_cols: list[str] = []

        for ct in safe_columns:
            old_name = ct["old_column_name"]
            new_name = ct["new_column_name"]
            col_type = old_col_types.get(old_name, "VARCHAR")
            select_parts.append(f"{quote_identifier(old_name)} AS {quote_identifier(new_name)}")
            create_cols.append(f"{quote_identifier(new_name)} {col_type}")

        create_sql = (
            f"CREATE OR REPLACE TABLE {quote_identifier(new_table)} (\n  "
            + ",\n  ".join(create_cols)
            + "\n);"
        )
        insert_sql = (
            f"INSERT INTO {quote_identifier(new_table)} SELECT "
            + ", ".join(select_parts)
            + f" FROM {quote_identifier(old_table)};"
        )
        full_sql = f"{create_sql}\n{insert_sql}"
        logger.info(f"Transform SQL:\n{full_sql[:500]}")
        self.db.sql(full_sql)

        # Table comment
        try:
            comment = transform.description.replace("'", "''")
            self.db.sql(f"COMMENT ON TABLE {quote_identifier(new_table)} IS '{comment}';")
        except Exception as e:
            logger.warning(f"Failed to add table comment: {e}")

        # Column comments
        for ct in safe_columns:
            try:
                desc = ct.get("column_description", "").replace("'", "''")
                self.db.sql(
                    f"COMMENT ON COLUMN {quote_identifier(new_table)}."
                    f"{quote_identifier(ct['new_column_name'])} IS '{desc}';"
                )
            except Exception as e:
                logger.warning(f"Failed to add column comment: {e}")

        self.table_name = new_table
        transform.columns = safe_columns
        return new_table

    def close(self) -> None:
        if self.db:
            self.db.close()
            self.db = None  # type: ignore[assignment]

    def __enter__(self) -> ExcelReader:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

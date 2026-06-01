"""SQL prompt builder with dialect-specific guidance."""

from typing import Optional


# Base system prompt for all databases
BASE_SYSTEM_PROMPT = """You are an expert data analyst. Given a database schema and a user question, generate a valid SQL query.
Rules:
1. Use only SELECT statements. Do not use INSERT, UPDATE, DELETE, DROP, or ALTER.
2. Use table and column names exactly as they appear in the schema.
3. If the question is ambiguous, make reasonable assumptions and comment them in the SQL as `-- assumption: ...`.
4. Return ONLY the SQL query, no markdown, no explanation.
"""

# Dialect-specific hints
DIALECT_HINTS = {
    "postgresql": """
PostgreSQL-specific notes:
- Use ILIKE for case-insensitive string matching
- Use ::type for casting (e.g., value::integer)
- Use LIMIT n OFFSET m for pagination
- Use COALESCE for null handling
""",
    "mysql": """
MySQL-specific notes:
- Use LIKE for case-insensitive string matching (default)
- Use CAST(value AS type) or CONVERT(value, type) for casting
- Use LIMIT n OFFSET m or LIMIT m, n for pagination
- Use IFNULL or COALESCE for null handling
""",
    "clickhouse": """
ClickHouse-specific notes:
- Use LIMIT n OFFSET m for pagination
- Use ifNull or coalesce for null handling
- Group by must include all non-aggregated columns
- Use toTypeName for type checking
""",
    "mssql": """
SQL Server-specific notes:
- Use TOP n for limiting results
- Use ISNULL for null handling
- Use CAST(value AS type) or CONVERT(type, value) for casting
- Use OFFSET n ROWS FETCH NEXT m ROWS ONLY for pagination
""",
    "oracle": """
Oracle-specific notes:
- Use ROWNUM <= n or FETCH FIRST n ROWS ONLY for limiting
- Use NVL for null handling
- Use TO_CHAR, TO_NUMBER, TO_DATE for type conversion
- Use || for string concatenation
""",
    "starrocks": """
StarRocks-specific notes:
- Uses MySQL protocol, follow MySQL syntax
- Use LIMIT n OFFSET m for pagination
- Use IFNULL or COALESCE for null handling
""",
    "vertica": """
Vertica-specific notes:
- Use LIMIT n OFFSET m for pagination
- Use NVL or COALESCE for null handling
- Use CAST(value AS type) for type conversion
""",
    "hive": """
Hive-specific notes:
- Use LIMIT n for limiting (no OFFSET support)
- Use COALESCE for null handling
- Use CAST(value AS type) for type conversion
- Many SQL functions may not be available
""",
    "sqlite": """
SQLite-specific notes:
- Use LIMIT n OFFSET m for pagination
- Use COALESCE or IFNULL for null handling
- Use CAST(value AS type) for type conversion
- Date functions use strftime
""",
    "duckdb": """
DuckDB-specific notes:
- Use LIMIT n OFFSET m for pagination
- Use COALESCE for null handling
- Use CAST(value AS type) or value::type for casting
- Supports many PostgreSQL-style functions
""",
}


def build_sql_prompt(schema: str, question: str, db_type: Optional[str] = None) -> str:
    """Build SQL prompt with dialect-specific hints.

    Args:
        schema: Database schema DDL
        question: User question to answer
        db_type: Database type for dialect-specific hints

    Returns:
        Complete prompt for SQL generation
    """
    # Get dialect-specific hints
    dialect_hint = ""
    if db_type and db_type.lower() in DIALECT_HINTS:
        dialect_hint = DIALECT_HINTS[db_type.lower()]

    return f"""{BASE_SYSTEM_PROMPT}
{dialect_hint}
Schema:
{schema}

Question: {question}

SQL:"""

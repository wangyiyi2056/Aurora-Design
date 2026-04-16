import json
from typing import Any, Optional

import httpx

from chatbi_core.agent.skill.base import BaseSkill
from chatbi_serve.datasource.service import DatasourceService


class SQLExecuteSkill(BaseSkill):
    """Execute arbitrary SQL against a datasource and return the results."""

    def __init__(
        self,
        datasource_service: Optional[DatasourceService] = None,
        datasource_name: str = "",
    ):
        self._datasource = datasource_service
        self._datasource_name = datasource_name

    @property
    def name(self) -> str:
        return "sql_execute"

    @property
    def description(self) -> str:
        return (
            "Execute a SQL query against the connected database and return the results. "
            "Use this for data exploration, validation, or when the user asks to run SQL."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to execute.",
                }
            },
            "required": ["sql"],
        }

    async def execute(self, sql: str = "", **kwargs: Any) -> str:
        if not sql:
            return "No SQL provided."
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
            success, result = connector.run(sql)
            if success:
                return f"SQL executed successfully.\n\nResult:\n{result}"
            return f"SQL execution failed:\n{result}"
        except Exception as e:
            return f"Error executing SQL: {e}"


class DatabaseSchemaSkill(BaseSkill):
    """Retrieve database schema information including tables, columns, and sample data."""

    def __init__(
        self,
        datasource_service: Optional[DatasourceService] = None,
        datasource_name: str = "",
    ):
        self._datasource = datasource_service
        self._datasource_name = datasource_name

    @property
    def name(self) -> str:
        return "database_schema"

    @property
    def description(self) -> str:
        return (
            "Get the database schema (tables, columns, types) and sample data. "
            "Use this before writing SQL to understand the data structure."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of table names to inspect. If empty, all tables are returned.",
                }
            },
            "required": [],
        }

    async def execute(self, tables: list[str] | None = None, **kwargs: Any) -> str:
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
            table_names = connector.get_table_names()
            if tables:
                table_names = [t for t in table_names if t in tables]

            if not table_names:
                return "No tables found in the datasource."

            schemas = connector.get_table_schemas(table_names)

            # Add sample data for each table
            samples = []
            for table in table_names[:5]:
                try:
                    sample = connector.query(f"SELECT * FROM {table} LIMIT 3")
                    samples.append(f"-- Sample from {table}:\n{json.dumps(sample, ensure_ascii=False, default=str)}")
                except Exception:
                    pass

            sample_text = "\n\n".join(samples)
            return f"Database Schema:\n\n{schemas}\n\n{sample_text}"
        except Exception as e:
            return f"Error retrieving schema: {e}"


class PythonAnalysisSkill(BaseSkill):
    """Execute Python code in a sandbox for complex data analysis, computation, or visualization."""

    def __init__(self, sandbox_url: str = "http://localhost:9000"):
        self._sandbox_url = sandbox_url

    @property
    def name(self) -> str:
        return "python_analysis"

    @property
    def description(self) -> str:
        return (
            "Execute Python code in a secure sandbox for complex data analysis, "
            "statistical computation, or when pandas/numpy is needed. "
            "If generating files like images or HTML, save them to /workspace/output/ and "
            "request them in output_files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute.",
                },
                "output_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of filenames to retrieve from /workspace/output/ after execution.",
                },
            },
            "required": ["code"],
        }

    async def execute(
        self, code: str = "", output_files: list[str] | None = None, **kwargs: Any
    ) -> str:
        if not code:
            return "No code provided."

        payload = {
            "code": code,
            "language": "python",
            "output_files": output_files or [],
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(f"{self._sandbox_url}/execute", json=payload)
                result = resp.json()
        except Exception as e:
            return f"Sandbox request failed: {e}"

        if not result.get("success"):
            return (
                f"Execution failed:\n"
                f"stdout: {result.get('stdout', '')}\n"
                f"stderr: {result.get('stderr', '')}"
            )

        output = f"stdout:\n{result.get('stdout', '')}"
        if result.get("stderr"):
            output += f"\n\nstderr:\n{result.get('stderr', '')}"

        files = result.get("files", {})
        for fname, b64 in files.items():
            if fname.endswith(".png"):
                output += f"\n\n![{fname}](data:image/png;base64,{b64})"
            elif fname.endswith(".html"):
                output += (
                    f"\n\n<{fname}>\n"
                    f'<iframe src="data:text/html;base64,{b64}" '
                    f'style="width:100%;height:400px;border:1px solid #ddd;border-radius:8px;"></iframe>'
                )
            else:
                output += f"\n\n[{fname}]\n{b64[:200]}..."

        return output

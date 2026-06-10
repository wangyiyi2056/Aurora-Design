import re
from typing import Optional, Tuple

from aurora_core.model.registry import ModelRegistry
from aurora_core.schema.message import Message
from aurora_serve.datasource.service import DatasourceService
from aurora_serve.prompt.sql_prompt import build_sql_prompt


class SQLAgent:
    def __init__(
        self,
        model_registry: ModelRegistry,
        datasource_service: DatasourceService,
        datasource_name: Optional[str] = None,
        max_retries: int = 2,
    ):
        self.registry = model_registry
        self.datasource = datasource_service
        self.datasource_name = datasource_name
        self.max_retries = max_retries

    def is_sql_question(self, text: str) -> bool:
        keywords = [
            "sql", "query", "table", "database", "select", "count", "sum", "avg",
            "top", "sales", "revenue", "user", "order", "product",
        ]
        lower = text.lower()
        return any(k in lower for k in keywords)

    async def run(
        self, question: str, datasource_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        ds_name = datasource_name or self.datasource_name
        if not ds_name:
            return False, "No datasource selected."

        connector = self.datasource.get_connector(ds_name)
        db_type = connector.db_type
        tables = connector.get_table_names()
        schema = connector.get_table_schemas(tables[:10])  # limit schema context

        llm = self.registry.get_llm()
        prompt = build_sql_prompt(schema, question, db_type)

        last_error = ""
        for attempt in range(self.max_retries + 1):
            messages = [Message(role="user", content=prompt)]
            output = await llm.achat(messages)
            sql = self._extract_sql(output.text)
            success, result = connector.run(sql)
            if success:
                formatted = self._format_result(result)
                return True, f"SQL:\n```sql\n{sql}\n```\n\nResult:\n{formatted}"
            last_error = result
            prompt = (
                f"The previous SQL query failed with error:\n{last_error}\n\n"
                f"Please fix the SQL and try again. Database type: {db_type}\n\n"
                f"Schema:\n{schema}\n\n"
                f"Question: {question}\n\nSQL:"
            )

        return False, f"Failed after {self.max_retries + 1} attempts. Last error: {last_error}"

    def _extract_sql(self, text: str) -> str:
        # Try to extract code block
        match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Try generic code block
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _format_result(self, result: list) -> str:
        """Format query result as Markdown table.

        Args:
            result: List of rows, first row is headers

        Returns:
            Markdown formatted table string
        """
        if not result or not isinstance(result, list):
            return str(result)

        # Check if result has headers (first row)
        if len(result) < 1:
            return "Empty result"

        # Handle case where result might be list of dicts
        if isinstance(result[0], dict):
            headers = list(result[0].keys())
            rows = [[str(row.get(h, "")) for h in headers] for row in result]
        elif isinstance(result[0], list):
            headers = result[0]
            rows = [[str(cell) if cell is not None else "" for cell in row] for row in result[1:]]
        else:
            return str(result)

        # Build markdown table
        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "| " + " | ".join(["---" for _ in headers]) + " |"
        row_lines = ["| " + " | ".join(row) + " |" for row in rows]

        return "\n".join([header_line, separator_line] + row_lines)

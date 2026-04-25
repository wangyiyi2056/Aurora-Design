import json
import re
from typing import Any, Optional

from chatbi_core.agent.skill.base import BaseSkill
from chatbi_core.schema.message import Message
from chatbi_serve.datasource.service import DatasourceService
from chatbi_core.model.adapter.openai_adapter import OpenAILLM


CHART_TYPE_PROMPT = """
Available chart types:
- response_table: suitable for display with many columns or non-numeric columns
- response_line_chart: used to display comparative trend analysis data
- response_bar_chart: used to compare values across categories
- response_pie_chart: suitable for proportion and distribution statistics
- response_scatter_chart: suitable for exploring relationships between variables
- response_area_chart: suitable for visualization of time series data
""".strip()


class SQLChartSkill(BaseSkill):
    """Generate a chart from natural language by producing SQL and chart type, then querying the database."""

    def __init__(
        self,
        llm: Optional[OpenAILLM] = None,
        datasource_service: Optional[DatasourceService] = None,
        datasource_name: str = "",
    ):
        self._llm = llm
        self._datasource = datasource_service
        self._datasource_name = datasource_name

    @property
    def name(self) -> str:
        return "sql_chart"

    @property
    def description(self) -> str:
        return (
            "Generate a chart from a natural language question. "
            "Requires the question to be provided. "
            "Outputs a vis-db-chart block with SQL result data."
        )

    @property
    def description_cn(self) -> str:
        return "根据自然语言问题生成图表，输出包含SQL结果数据的vis-db-chart块。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The natural language question describing what chart to generate.",
                }
            },
            "required": ["question"],
        }

    async def execute(self, question: str = "", **kwargs: Any) -> str:
        if not question:
            return "No question provided."
        if not self._llm:
            return "LLM not available for chart generation."
        if not self._datasource:
            return "Datasource service not available."

        ds_name = kwargs.get("datasource_name") or self._datasource_name
        if not ds_name:
            return "No datasource selected."

        try:
            connector = self._datasource.get_connector(ds_name)
        except Exception as e:
            return f"Datasource error: {e}"

        tables = connector.get_table_names()
        schema = connector.get_table_schemas(tables[:10])

        # Step 1: ask LLM for SQL + chart type
        prompt = self._build_prompt(schema, question)
        messages = [Message(role="user", content=prompt)]
        output = await self._llm.achat(messages)
        parsed = self._parse_output(output.text)

        sql = parsed.get("sql", "")
        display_type = parsed.get("display_type", "response_table")
        thought = parsed.get("thought", "")

        if not sql:
            return f"Failed to generate SQL. LLM output:\n{output.text}"

        # Step 2: execute SQL
        success, result = connector.run(sql)
        if not success:
            return f"SQL execution failed: {result}\n\nGenerated SQL: {sql}"

        # Step 3: build vis-db-chart JSON
        data = []
        if isinstance(result, list):
            data = result
        elif isinstance(result, str):
            # Try to parse if it's a table-like string
            data = self._parse_result_to_list(result)

        payload = {
            "sql": sql,
            "type": display_type,
            "title": thought or "Chart",
            "describe": thought,
            "data": data,
        }

        return f"```vis-db-chart\n{json.dumps(payload, ensure_ascii=False)}\n```"

    def _build_prompt(self, schema: str, question: str) -> str:
        return (
            "You are a data analyst. Given the database schema below, "
            "write a SQL query to answer the user's question, and choose the most "
            "appropriate chart type.\n\n"
            f"{CHART_TYPE_PROMPT}\n\n"
            "Respond ONLY in this JSON format (no markdown code blocks):\n"
            '{"sql": "...", "display_type": "...", "thought": "..."}\n\n'
            f"Schema:\n{schema}\n\n"
            f"Question: {question}"
        )

    def _parse_output(self, text: str) -> dict[str, str]:
        # Try to extract JSON from code block or raw text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def _parse_result_to_list(self, result: str) -> list[dict[str, Any]]:
        lines = result.strip().splitlines()
        if len(lines) < 2:
            return []
        headers = [h.strip() for h in lines[0].split("|") if h.strip()]
        data = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split("|")]
            if len(values) == len(headers):
                data.append(dict(zip(headers, values)))
        return data


class SQLDashboardSkill(BaseSkill):
    """Generate a dashboard from natural language by producing multiple SQL + chart types."""

    def __init__(
        self,
        llm: Optional[OpenAILLM] = None,
        datasource_service: Optional[DatasourceService] = None,
        datasource_name: str = "",
    ):
        self._llm = llm
        self._datasource = datasource_service
        self._datasource_name = datasource_name

    @property
    def name(self) -> str:
        return "sql_dashboard"

    @property
    def description(self) -> str:
        return (
            "Generate a dashboard from a natural language question. "
            "Outputs a vis-dashboard block with multiple chart data."
        )

    @property
    def description_cn(self) -> str:
        return "根据自然语言问题生成仪表板，输出包含多个图表数据的vis-dashboard块。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The natural language question describing what dashboard to generate.",
                }
            },
            "required": ["question"],
        }

    async def execute(self, question: str = "", **kwargs: Any) -> str:
        if not question:
            return "No question provided."
        if not self._llm or not self._datasource:
            return "LLM or datasource service not available."

        ds_name = kwargs.get("datasource_name") or self._datasource_name
        if not ds_name:
            return "No datasource selected."

        try:
            connector = self._datasource.get_connector(ds_name)
        except Exception as e:
            return f"Datasource error: {e}"

        tables = connector.get_table_names()
        schema = connector.get_table_schemas(tables[:10])

        prompt = self._build_prompt(schema, question)
        messages = [Message(role="user", content=prompt)]
        output = await self._llm.achat(messages)
        parsed = self._parse_output(output.text)

        charts = []
        chart_items = parsed if isinstance(parsed, list) else [parsed]

        for item in chart_items:
            sql = item.get("sql", "")
            display_type = item.get("display_type", "response_table")
            title = item.get("title", "Chart")
            thought = item.get("thought", "")

            chart_data = []
            err_msg = None
            if sql:
                success, result = connector.run(sql)
                if success:
                    if isinstance(result, list):
                        chart_data = result
                    else:
                        chart_data = self._parse_result_to_list(result)
                else:
                    err_msg = str(result)

            charts.append({
                "sql": sql,
                "type": display_type,
                "title": title,
                "describe": thought,
                "data": chart_data,
                "err_msg": err_msg,
            })

        payload = {
            "data": charts,
            "chart_count": len(charts),
            "title": question,
            "display_strategy": "default",
            "style": "default",
        }

        return f"```vis-dashboard\n{json.dumps(payload, ensure_ascii=False)}\n```"

    def _build_prompt(self, schema: str, question: str) -> str:
        return (
            "You are a data analyst. Given the database schema below, "
            "write multiple SQL queries to build a dashboard that answers the user's question. "
            "Choose an appropriate chart type for each query.\n\n"
            f"{CHART_TYPE_PROMPT}\n\n"
            "Respond ONLY as a JSON array (no markdown code blocks):\n"
            '[{"sql": "...", "display_type": "...", "title": "...", "thought": "..."}]\n\n'
            f"Schema:\n{schema}\n\n"
            f"Question: {question}"
        )

    def _parse_output(self, text: str) -> Any:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        # Fallback: try to parse as single object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def _parse_result_to_list(self, result: str) -> list[dict[str, Any]]:
        lines = result.strip().splitlines()
        if len(lines) < 2:
            return []
        headers = [h.strip() for h in lines[0].split("|") if h.strip()]
        data = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split("|")]
            if len(values) == len(headers):
                data.append(dict(zip(headers, values)))
        return data

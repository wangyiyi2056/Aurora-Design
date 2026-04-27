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
            "Outputs a self-contained HTML page with ECharts."
        )

    @property
    def description_cn(self) -> str:
        return "根据自然语言问题生成图表，输出包含ECharts的完整HTML页面。"

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

        # Step 3: build HTML with ECharts
        data: list[Any] = []
        if isinstance(result, list):
            data = result
        elif isinstance(result, str):
            data = self._parse_result_to_list(result)

        data_json = json.dumps(data, ensure_ascii=False)
        title = thought or "Chart"
        chart_type_map = {
            "response_bar_chart": "bar",
            "response_line_chart": "line",
            "response_pie_chart": "pie",
            "response_scatter_chart": "scatter",
            "response_area_chart": "line",
        }
        echarts_type = chart_type_map.get(display_type, "bar")
        series_map = {
            "bar": f'{{name: "{title}", type: "bar", data: rawData.map(d => d[columns[1]])}}',
            "line": f'{{name: "{title}", type: "line", data: rawData.map(d => d[columns[1]])}}',
            "pie": f'{{name: "{title}", type: "pie", data: rawData.map(d => ({{name: d[columns[0]], value: d[columns[1]]}}))}}',
            "scatter": f'{{name: "{title}", type: "scatter", data: rawData.map(d => [d[columns[0]], d[columns[1]]])}}',
        }
        series_config = series_map.get(echarts_type, series_map["bar"])

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
body{{margin:0;padding:24px;font-family:system-ui,-apple-system,sans-serif;background:#fff}}
h2{{margin:0 0 16px;font-size:18px;color:#333}}
#chart{{width:100%;height:400px}}
</style>
</head>
<body>
<h2>{title}</h2>
<div id="chart"></div>
<script>
var rawData = {data_json};
var columns = Object.keys(rawData[0] || {{}});
var chart = echarts.init(document.getElementById("chart"));
chart.setOption({{
  tooltip: {{trigger: "axis"}},
  xAxis: echarts_type === "pie" ? null : {{type: "category", data: rawData.map(d => d[columns[0]])}},
  yAxis: echarts_type === "pie" ? null : {{type: "value"}},
  series: [{series_config}]
}});
</script>
</body>
</html>"""

        return f"```web\n{html}\n```"

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
            "Outputs a self-contained HTML dashboard with ECharts."
        )

    @property
    def description_cn(self) -> str:
        return "根据自然语言问题生成仪表板，输出包含ECharts的完整HTML页面。"

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

        chart_type_map = {
            "response_bar_chart": "bar",
            "response_line_chart": "line",
            "response_pie_chart": "pie",
            "response_scatter_chart": "scatter",
            "response_area_chart": "line",
        }

        chart_scripts: list[str] = []
        chart_divs: list[str] = []
        for i, c in enumerate(charts):
            data_json = json.dumps(c.get("data", []), ensure_ascii=False)
            title = c.get("title", f"Chart {i+1}")
            t = c.get("type", "response_bar_chart")
            echarts_type = chart_type_map.get(t, "bar")
            chart_divs.append(
                f'<h3>{title}</h3><div id="chart{i}" style="width:100%;height:350px"></div>'
            )
            chart_scripts.append(f"""
(function() {{
  var data = {data_json};
  if (!data.length) return;
  var cols = Object.keys(data[0]);
  var chart = echarts.init(document.getElementById("chart{i}"));
  chart.setOption({{
    tooltip: {{trigger: 'axis'}},
    xAxis: '{echarts_type}' === 'pie' ? null : {{type: 'category', data: data.map(d => d[cols[0]])}},
    yAxis: '{echarts_type}' === 'pie' ? null : {{type: 'value'}},
    series: ['{echarts_type}' === 'pie'
      ? {{name: '{title}', type: 'pie', data: data.map(d => ({{name: d[cols[0]], value: d[cols[1]]}}))}}
      : {{name: '{title}', type: '{echarts_type}', data: data.map(d => d[cols[1]])}}]
  }});
}})();""")

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
body{{margin:0;padding:24px;font-family:system-ui,-apple-system,sans-serif;background:#fff}}
h2{{margin:0 0 20px;font-size:22px;color:#333}}
h3{{margin:16px 0 8px;font-size:16px;color:#555}}
</style>
</head>
<body>
<h2>{question}</h2>
{"".join(chart_divs)}
<script>
{"".join(chart_scripts)}
</script>
</body>
</html>"""

        return f"```web\n{html}\n```"

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

"""Enhanced CSV Analysis Skill with pandas and chart recommendations."""

import io
import json
import re
from typing import Any

import pandas as pd

from aurora_core.agent.skill.base import BaseSkill


CHART_TYPE_PROMPT = """
Available chart types:
- response_table: suitable for display with many columns or non-numeric columns
- response_line_chart: used to display comparative trend analysis data
- response_bar_chart: used to compare values across categories
- response_pie_chart: suitable for proportion and distribution statistics
- response_scatter_chart: suitable for exploring relationships between variables
- response_area_chart: suitable for visualization of time series data
""".strip()


class CSVAnalysisSkill(BaseSkill):
    """Enhanced CSV analysis skill with pandas and chart recommendations."""

    @property
    def name(self) -> str:
        return "csv_analysis"

    @property
    def description(self) -> str:
        return (
            "Analyze CSV/Excel data and return statistics, column types, and chart recommendations. "
            "Output includes structured JSON that can be used to generate vis-db-chart visualizations."
        )

    @property
    def description_cn(self) -> str:
        return "分析CSV/Excel数据，返回统计信息、列类型推断和图表推荐。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "csv_content": {
                    "type": "string",
                    "description": "The raw CSV/Excel content to analyze. May include file header prefix.",
                }
            },
            "required": ["csv_content"],
        }

    def _extract_csv_content(self, content: str) -> str:
        """Extract actual CSV content from potential file attachment format."""
        # Handle [Attached file: filename]\n prefix
        pattern = r"^\[Attached file: [^\]]+\]\n"
        match = re.match(pattern, content)
        if match:
            return content[match.end():]
        return content

    def _infer_column_type(self, series: pd.Series) -> str:
        """Infer the semantic type of a column."""
        dtype = str(series.dtype)

        if "datetime" in dtype or "date" in dtype:
            return "date"
        if "int" in dtype or "float" in dtype:
            # Check if it looks like categorical (few unique values)
            unique_ratio = series.nunique() / len(series)
            if unique_ratio < 0.05 and series.nunique() <= 10:
                return "category"
            return "number"
        if "object" in dtype or "string" in dtype:
            # Check for date-like strings
            try:
                pd.to_datetime(series.head(10), errors="raise")
                return "date"
            except (ValueError, TypeError):
                pass
            # Check if categorical
            unique_ratio = series.nunique() / len(series)
            if unique_ratio < 0.5:
                return "category"
            return "text"
        return "unknown"

    def _recommend_chart(self, df: pd.DataFrame, column_types: dict[str, str]) -> list[dict[str, Any]]:
        """Recommend suitable chart types based on data characteristics."""
        recommendations = []

        # Get columns by type
        date_cols = [c for c, t in column_types.items() if t == "date"]
        category_cols = [c for c, t in column_types.items() if t == "category"]
        number_cols = [c for c, t in column_types.items() if t == "number"]
        text_cols = [c for c, t in column_types.items() if t == "text"]

        # Skip if no numeric columns
        if not number_cols:
            return [{"chart_type": "response_table", "reason": "No numeric columns for visualization"}]

        # 1. Time series chart (line/area) - if we have date + number
        if date_cols and number_cols:
            x_key = date_cols[0]
            y_key = number_cols[0]
            recommendations.append({
                "chart_type": "response_line_chart",
                "x_key": x_key,
                "y_key": y_key,
                "reason": f"Time series data: {x_key} (date) vs {y_key} (number)",
            })
            if len(number_cols) > 1:
                recommendations.append({
                    "chart_type": "response_area_chart",
                    "x_key": x_key,
                    "y_keys": number_cols[:3],  # Top 3 numeric columns
                    "reason": f"Multi-series time series: {x_key} vs {', '.join(number_cols[:3])}",
                })

        # 2. Bar chart - if we have category + number
        if category_cols and number_cols:
            x_key = category_cols[0]
            y_key = number_cols[0]
            cat_unique = df[x_key].nunique()
            if cat_unique <= 20:  # Reasonable number of bars
                recommendations.append({
                    "chart_type": "response_bar_chart",
                    "x_key": x_key,
                    "y_key": y_key,
                    "reason": f"Comparison: {x_key} ({cat_unique} categories) vs {y_key}",
                })

        # 3. Pie chart - if we have category + number with few categories
        if category_cols and number_cols:
            x_key = category_cols[0]
            y_key = number_cols[0]
            cat_unique = df[x_key].nunique()
            if 2 <= cat_unique <= 8:  # Good for pie chart
                recommendations.append({
                    "chart_type": "response_pie_chart",
                    "x_key": x_key,
                    "y_key": y_key,
                    "reason": f"Proportion: {x_key} ({cat_unique} categories) by {y_key}",
                })

        # 4. Scatter chart - if we have 2+ numeric columns
        if len(number_cols) >= 2:
            recommendations.append({
                "chart_type": "response_scatter_chart",
                "x_key": number_cols[0],
                "y_key": number_cols[1],
                "reason": f"Correlation: {number_cols[0]} vs {number_cols[1]}",
            })

        # 5. Default table if text columns dominate
        if len(text_cols) > len(number_cols) and not recommendations:
            recommendations.append({
                "chart_type": "response_table",
                "reason": "Text-heavy data, better displayed as table",
            })

        # Ensure at least one recommendation
        if not recommendations:
            recommendations.append({
                "chart_type": "response_bar_chart",
                "x_key": category_cols[0] if category_cols else df.columns[0],
                "y_key": number_cols[0],
                "reason": "Default bar chart for numeric data",
            })

        return recommendations

    async def execute(self, csv_content: str, **kwargs: Any) -> str:
        """Execute CSV analysis and return structured JSON."""
        try:
            # Extract actual CSV content
            content = self._extract_csv_content(csv_content)

            # Try to parse as CSV or Excel
            try:
                df = pd.read_csv(io.StringIO(content))
            except pd.errors.ParserError:
                # Try Excel format
                df = pd.read_excel(io.StringIO(content))

            if df.empty:
                return json.dumps({"error": "No data found"}, ensure_ascii=False)

            # Basic statistics
            row_count = len(df)
            col_count = len(df.columns)
            columns = list(df.columns)

            # Infer column types
            column_types = {col: self._infer_column_type(df[col]) for col in columns}

            # Column metadata
            column_info = []
            for col in columns:
                col_type = column_types[col]
                col_data = df[col]
                info = {
                    "name": col,
                    "type": col_type,
                    "dtype": str(col_data.dtype),
                    "null_count": int(col_data.isna().sum()),
                }
                if col_type == "number":
                    info["min"] = float(col_data.min()) if pd.notna(col_data.min()) else None
                    info["max"] = float(col_data.max()) if pd.notna(col_data.max()) else None
                    info["mean"] = float(col_data.mean()) if pd.notna(col_data.mean()) else None
                elif col_type in ("category", "text"):
                    info["unique_count"] = int(col_data.nunique())
                    if col_type == "category" and col_data.nunique() <= 10:
                        # Top 5 value frequencies
                        freq = col_data.value_counts().head(5)
                        info["top_values"] = [{"value": str(v), "count": int(c)} for v, c in freq.items()]
                column_info.append(info)

            # Preview (first 10 rows)
            preview_df = df.head(10)
            preview = json.loads(
                preview_df.to_json(orient="records", date_format="iso", force_ascii=False)
            )

            # Full data (for chart generation) - limit to 100 rows for safety
            data_df = df.head(100)
            full_data = json.loads(
                data_df.to_json(orient="records", date_format="iso", force_ascii=False)
            )

            # Chart recommendations
            recommendations = self._recommend_chart(df, column_types)

            # Build result
            result = {
                "summary": f"CSV analyzed: {row_count} rows, {col_count} columns. "
                           f"Numeric columns: {len([c for c, t in column_types.items() if t == 'number'])}. "
                           f"Recommended chart: {recommendations[0]['chart_type']}",
                "row_count": row_count,
                "column_count": col_count,
                "columns": column_info,
                "preview": preview,
                "data": full_data,
                "recommendations": recommendations,
                "chart_prompt": CHART_TYPE_PROMPT,
            }

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": f"CSV analysis failed: {str(e)}"}, ensure_ascii=False)
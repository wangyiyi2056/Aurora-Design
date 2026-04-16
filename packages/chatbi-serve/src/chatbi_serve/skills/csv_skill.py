import csv
import io
from typing import Any

from chatbi_core.agent.skill.base import BaseSkill


class CSVAnalysisSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "csv_analysis"

    @property
    def description(self) -> str:
        return "Analyze a CSV string and return basic statistics (row count, column names, first 5 rows)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "csv_content": {
                    "type": "string",
                    "description": "The raw CSV content to analyze.",
                }
            },
            "required": ["csv_content"],
        }

    async def execute(self, csv_content: str, **kwargs: Any) -> str:
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)
            if not rows:
                return "No data found in CSV."
            columns = list(rows[0].keys())
            preview = rows[:5]
            return (
                f"Rows: {len(rows)}\n"
                f"Columns: {columns}\n"
                f"Preview: {preview}"
            )
        except Exception as e:
            return f"CSV analysis failed: {e}"

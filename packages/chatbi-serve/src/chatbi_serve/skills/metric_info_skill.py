import json
from typing import Any, Optional

from chatbi_core.agent.skill.base import BaseSkill


class MetricInfoSkill(BaseSkill):
    """Retrieve and return metric metadata information."""

    @property
    def name(self) -> str:
        return "metric_info"

    @property
    def description(self) -> str:
        return (
            "Retrieve structured metadata for a metric. "
            "Use this to document or look up metric definitions, calculation rules, "
            "and suggested dimensions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "The name of the metric to retrieve information for.",
                },
                "field_name": {
                    "type": "string",
                    "description": "The field name of the metric in the database.",
                },
                "calculation_rule": {
                    "type": "string",
                    "description": "The calculation rule or formula for the metric (optional).",
                },
                "suggested_dimension": {
                    "type": "string",
                    "description": "Suggested dimension for analyzing the metric (optional).",
                },
                "threshold": {
                    "type": "number",
                    "description": "Optional threshold value for the metric.",
                },
            },
            "required": ["metric_name", "field_name"],
        }

    async def execute(
        self,
        metric_name: str = "",
        field_name: str = "",
        calculation_rule: Optional[str] = None,
        suggested_dimension: Optional[str] = None,
        threshold: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        result = {
            "metric_name": metric_name,
            "field_name": field_name,
            "calculation_rule": calculation_rule,
            "suggested_dimension": suggested_dimension,
            "threshold": threshold,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

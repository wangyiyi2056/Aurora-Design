import json
from typing import Any, Optional

from aurora_core.agent.skill.base import BaseSkill


class VolatilityAnalysisSkill(BaseSkill):
    """Perform factor-level volatility / attribution analysis."""

    @property
    def name(self) -> str:
        return "volatility_analysis"

    @property
    def description(self) -> str:
        return (
            "Perform volatility attribution analysis across dimensions. "
            "Given a metric, baseline/current totals, and factor-level values, "
            "computes absolute changes and contribution rates for each factor. "
            "Use this after querying baseline and current data with sql_execute."
        )

    @property
    def description_cn(self) -> str:
        return "执行指标波动归因分析，计算各因素的绝对变化和贡献率。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "The name of the metric being analyzed.",
                },
                "baseline_total": {
                    "type": "number",
                    "description": "The baseline period total value of the metric.",
                },
                "current_total": {
                    "type": "number",
                    "description": "The current period total value of the metric.",
                },
                "baseline_time_range": {
                    "type": "string",
                    "description": "The baseline time range (e.g., '2024-01-01 to 2024-01-31').",
                },
                "current_time_range": {
                    "type": "string",
                    "description": "The current time range (e.g., '2024-02-01 to 2024-02-29').",
                },
                "dimension": {
                    "type": "string",
                    "description": "The dimension used for attribution analysis (e.g., 'region', 'product').",
                },
                "factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "factor": {"type": "string"},
                            "baseline_value": {"type": "number"},
                            "current_value": {"type": "number"},
                        },
                        "required": ["factor", "baseline_value", "current_value"],
                    },
                    "description": "List of factor-level baseline and current values.",
                },
            },
            "required": [
                "metric_name",
                "baseline_total",
                "current_total",
                "baseline_time_range",
                "current_time_range",
                "dimension",
                "factors",
            ],
        }

    async def execute(
        self,
        metric_name: str = "",
        baseline_total: float = 0.0,
        current_total: float = 0.0,
        baseline_time_range: str = "",
        current_time_range: str = "",
        dimension: str = "",
        factors: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        factors = factors or []
        total_change = current_total - baseline_total

        factor_data = []
        for item in factors:
            baseline_val = float(item.get("baseline_value", 0))
            current_val = float(item.get("current_value", 0))
            absolute_change = current_val - baseline_val
            contribution_rate = absolute_change / total_change if total_change != 0 else 0.0
            factor_data.append(
                {
                    "factor": str(item.get("factor", "")),
                    "baseline_value": baseline_val,
                    "current_value": current_val,
                    "absolute_change": round(absolute_change, 4),
                    "contribution_rate": round(contribution_rate, 4),
                }
            )

        factor_data.sort(key=lambda x: x["contribution_rate"], reverse=True)

        result = {
            "metric_name": metric_name,
            "dimension": dimension,
            "baseline_total": baseline_total,
            "current_total": current_total,
            "total_change": total_change,
            "baseline_time_range": baseline_time_range,
            "current_time_range": current_time_range,
            "factors": factor_data,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

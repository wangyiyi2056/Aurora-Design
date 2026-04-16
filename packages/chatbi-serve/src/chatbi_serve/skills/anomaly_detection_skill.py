import json
from typing import Any

from chatbi_core.agent.skill.base import BaseSkill


class AnomalyDetectionSkill(BaseSkill):
    """Detect anomalies by comparing baseline and current metric values."""

    @property
    def name(self) -> str:
        return "anomaly_detection"

    @property
    def description(self) -> str:
        return (
            "Detect anomalies by comparing a baseline metric value to a current value. "
            "Returns whether the fluctuation exceeds the given threshold."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "The name of the metric being analyzed.",
                },
                "baseline_value": {
                    "type": "number",
                    "description": "The baseline period value of the metric.",
                },
                "current_value": {
                    "type": "number",
                    "description": "The current period value of the metric.",
                },
                "threshold": {
                    "type": "number",
                    "description": "The threshold for determining anomalies (e.g., 0.1 for 10%).",
                },
            },
            "required": ["metric_name", "baseline_value", "current_value", "threshold"],
        }

    async def execute(
        self,
        metric_name: str = "",
        baseline_value: float = 0.0,
        current_value: float = 0.0,
        threshold: float = 0.1,
        **kwargs: Any,
    ) -> str:
        try:
            if baseline_value == 0:
                fluctuation_rate = float("inf") if current_value > 0 else 0.0
            else:
                fluctuation_rate = (current_value - baseline_value) / baseline_value

            is_anomaly = abs(fluctuation_rate) > threshold
            anomaly_type = "none"
            if is_anomaly:
                anomaly_type = "increase" if fluctuation_rate > 0 else "decrease"

            result = {
                "metric_name": metric_name,
                "baseline_value": baseline_value,
                "current_value": current_value,
                "fluctuation_rate": fluctuation_rate,
                "threshold": threshold,
                "is_anomaly": is_anomaly,
                "anomaly_type": anomaly_type,
                "recommend_next_step": (
                    "Proceed to volatility analysis or investigate root causes."
                    if is_anomaly
                    else "No further analysis needed."
                ),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Anomaly detection failed: {e}"

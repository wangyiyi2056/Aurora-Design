import json
import logging
from typing import Any, Optional

import requests

from chatbi_core.agent.skill.base import BaseSkill

logger = logging.getLogger(__name__)


class IndicatorSkill(BaseSkill):
    """Call an external API indicator and return the response."""

    @property
    def name(self) -> str:
        return "indicator"

    @property
    def description(self) -> str:
        return (
            "Call an external API indicator/tool. "
            "Use this to fetch metrics, query external services, or invoke REST APIs."
        )

    @property
    def description_cn(self) -> str:
        return "调用外部API指标/工具，用于获取指标数据或调用REST API。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "indicator_name": {
                    "type": "string",
                    "description": "Name of the indicator or API endpoint.",
                },
                "api": {
                    "type": "string",
                    "description": "The API URL to call.",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, PUT, DELETE).",
                    "enum": ["GET", "POST", "PUT", "DELETE", "get", "post", "put", "delete"],
                },
                "args": {
                    "type": "object",
                    "description": "Parameters to pass to the API (query params for GET, JSON body for POST).",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers.",
                },
                "thought": {
                    "type": "string",
                    "description": "Summary of why this API is being called.",
                },
            },
            "required": ["indicator_name", "api", "method"],
        }

    async def execute(
        self,
        indicator_name: str = "",
        api: str = "",
        method: str = "GET",
        args: Optional[dict] = None,
        headers: Optional[dict] = None,
        thought: str = "",
        **kwargs: Any,
    ) -> str:
        if not api:
            return "No API URL provided."

        args = args or {}
        headers = headers or {}
        method_upper = method.upper()

        try:
            if method_upper == "GET":
                resp = requests.get(api, params=args, headers=headers, timeout=30)
            elif method_upper == "POST":
                resp = requests.post(api, json=args, headers=headers, timeout=30)
            elif method_upper == "PUT":
                resp = requests.put(api, json=args, headers=headers, timeout=30)
            elif method_upper == "DELETE":
                resp = requests.delete(api, params=args, headers=headers, timeout=30)
            else:
                resp = requests.request(
                    method_upper, api, data=args, headers=headers, timeout=30
                )

            resp.raise_for_status()
            result_text = resp.text
            logger.info(f"Indicator '{indicator_name}' API result: {result_text[:500]}")

            output = {
                "indicator_name": indicator_name,
                "api": api,
                "method": method_upper,
                "status": "success",
                "result": result_text,
                "thought": thought,
            }
            return json.dumps(output, ensure_ascii=False, indent=2)
        except requests.HTTPError as e:
            return (
                f"Indicator '{indicator_name}' HTTP error: {e}\n"
                f"Response: {getattr(e.response, 'text', '')[:500]}"
            )
        except Exception as e:
            logger.exception(f"Indicator '{indicator_name}' execution failed")
            return f"Indicator '{indicator_name}' execution failed: {e}"

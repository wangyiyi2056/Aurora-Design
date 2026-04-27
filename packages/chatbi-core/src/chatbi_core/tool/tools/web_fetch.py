"""WebFetchTool — fetch URL contents. Ported from Claude-Code's WebFetchTool."""
from typing import Any, Dict, Optional

import httpx

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "WebFetch"
TOOL_DESCRIPTION = """Fetch content from a URL.
Use this to retrieve web pages, API responses, or any web-accessible content.
Returns the content as text, with HTML converted to markdown."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "The URL to fetch.",
        },
        "max_length": {
            "type": "integer",
            "description": "Maximum characters to return (default: 10000).",
        },
    },
    "required": ["url"],
}


async def web_fetch_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Fetch a URL and return its content."""
    url = args.get("url", "")
    max_length = args.get("max_length", 10000)

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ChatBI/1.0)",
        "Accept": "text/html,application/json,*/*",
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            content = resp.text
    except httpx.HTTPStatusError as e:
        return ToolResult(data=f"HTTP error {e.response.status_code}: {e.response.text[:200]}")
    except httpx.RequestError as e:
        return ToolResult(data=f"Request error: {e}")
    except Exception as e:
        return ToolResult(data=f"Error fetching {url}: {e}")

    if len(content) > max_length:
        content = content[:max_length] + "\n\n... [truncated]"

    return ToolResult(data=content)


async def web_fetch_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    url = args.get("url", "")
    if not url:
        return ValidationResult.fail("url is required")
    if not url.startswith(("http://", "https://")):
        return ValidationResult.fail("url must start with http:// or https://")
    return ValidationResult.ok()


WebFetchTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=web_fetch_call,
    validate_input_fn=web_fetch_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
    is_open_world_fn=lambda _: True,
    get_activity_description_fn=lambda args: f"Fetching {args.get('url', '')}",
    get_tool_use_summary_fn=lambda args: f"Fetch {args.get('url', '')}",
)

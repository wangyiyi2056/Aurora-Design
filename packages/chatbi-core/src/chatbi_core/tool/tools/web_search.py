"""WebSearchTool — search the web. Ported from Claude-Code's WebSearchTool."""
from typing import Any, Dict, Optional

import httpx

from chatbi_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "WebSearch"
TOOL_DESCRIPTION = """Search the web for information.
Use this to find current information, documentation, news, or any web content.
Returns search results with titles, snippets, and URLs."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results (default: 5).",
        },
    },
    "required": ["query"],
}


async def web_search_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Execute a web search."""
    query = args.get("query", "")
    max_results = args.get("max_results", 5)

    # Use a simple search API
    search_url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(search_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return ToolResult(data=f"Search error: {e}")

    # Parse results
    results = []
    abstract = data.get("AbstractText", "")
    if abstract:
        source = data.get("AbstractSource", "")
        url = data.get("AbstractURL", "")
        results.append(f"## {abstract[:200]}\nSource: {source}\nURL: {url}\n")

    related = data.get("RelatedTopics", [])
    for topic in related[:max_results]:
        if "Text" in topic:
            text = topic.get("Text", "")
            url = topic.get("FirstURL", "")
            results.append(f"- {text[:200]}\n  {url}\n")
        elif "Topics" in topic:
            for sub in topic["Topics"][:3]:
                text = sub.get("Text", "")
                url = sub.get("FirstURL", "")
                results.append(f"- {text[:200]}\n  {url}\n")

    if not results:
        results.append(f"No results found for '{query}'")

    return ToolResult(data="\n".join(results))


async def web_search_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("query"):
        return ValidationResult.fail("query is required")
    return ValidationResult.ok()


WebSearchTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=web_search_call,
    validate_input_fn=web_search_validate,
    is_concurrency_safe_fn=lambda _: True,
    is_read_only_fn=lambda _: True,
    is_open_world_fn=lambda _: True,
    get_activity_description_fn=lambda args: f"Searching: {args.get('query', '')}",
    get_tool_use_summary_fn=lambda args: f"Search {args.get('query', '')[:60]}",
)

"""ApiCall — Parse <api-call> XML from LLM output, execute SQL, generate vis-chart protocol.

Uses regex-based parsing tolerant of malformed LLM-generated XML.
Outputs ```vis-chart JSON blocks for frontend chart rendering.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chatbi_serve.excel.reader import ExcelReader

logger = logging.getLogger(__name__)

_API_CALL_RE = re.compile(r"<api-call>(.*?)</api-call>", re.DOTALL)
_NAME_RE = re.compile(r"<name>(.*?)</name>", re.DOTALL)
_SQL_RE = re.compile(r"<sql>(.*?)</sql>", re.DOTALL)
# Fallback when LLM uses markdown fences INSTEAD of <sql> tags
_FALLBACK_SQL_RE = re.compile(
    r"</name>\s*<args\s*>\s*(.*?)(?:</sql>|</args>|$)",
    re.DOTALL,
)

# Markdown code fences LLMs may inject inside <api-call>
_MD_FENCE_RE = re.compile(r"```(?:sql|xml|json|python|markdown)?\s*", re.DOTALL)

# SQL comments: single-line (-- ...) and block (/* ... */)
_SQL_COMMENT_RE = re.compile(r"--[^\n]*|/\*[\s\S]*?\*/")


@dataclass
class ParsedApiCall:
    name: str
    sql: str


@dataclass
class ChartResult:
    chart_type: str
    sql: str
    data: list[dict[str, Any]]
    error: str | None = None


def _remove_sql_comments(sql: str) -> str:
    """Remove single-line and block comments from SQL."""
    return _SQL_COMMENT_RE.sub("", sql)


def _clean_sql(raw_sql: str) -> str:
    """Normalize LLM-generated SQL: strip comments, fences, escaped chars."""
    sql = raw_sql.strip()
    # Remove markdown fences
    sql = _MD_FENCE_RE.sub("", sql)
    # Remove SQL comments (LLMs sometimes inject them)
    sql = _remove_sql_comments(sql)
    # Fix escaped underscores and newlines
    sql = sql.replace("\\_", "_").replace("\\n", " ").replace("\\", " ")
    # Collapse multiple blank lines
    sql = re.sub(r"\n\s*\n", "\n", sql)
    return sql.strip()


class ApiCall:
    """Parse <api-call> XML, execute SQL, generate vis-chart protocol for frontend."""

    @staticmethod
    def parse_api_calls(text: str) -> list[ParsedApiCall]:
        """Extract all <api-call> blocks from LLM output text.

        Tolerant of:
        - SQL wrapped in markdown code fences inside <api-call>
        - Whitespace/line breaks
        - Multiple api-call blocks
        """
        results: list[ParsedApiCall] = []
        for match in _API_CALL_RE.finditer(text):
            block = match.group(1)
            # Remove markdown fences inside the block
            block = _MD_FENCE_RE.sub("", block)

            name_match = _NAME_RE.search(block)
            sql_match = _SQL_RE.search(block)

            if not name_match:
                logger.warning(f"Could not parse api-call block (no <name>): {block[:200]}")
                continue

            name = name_match.group(1).strip()

            if not sql_match:
                # Fallback: LLM used markdown fences instead of <sql> tags
                fb = _FALLBACK_SQL_RE.search(block)
                if fb:
                    sql = _clean_sql(fb.group(1))
                else:
                    logger.warning(f"Could not extract SQL from api-call block, name={name}")
                    continue
            else:
                sql = _clean_sql(sql_match.group(1))

            if not sql:
                logger.warning(f"Empty SQL in api-call block, name={name}")
                continue

            results.append(ParsedApiCall(name=name, sql=sql))

        return results

    @staticmethod
    def execute_chart(parsed: ParsedApiCall, reader: ExcelReader) -> ChartResult:
        """Execute the SQL from a parsed api-call and return chart data."""
        try:
            df = reader.run_sql_df(parsed.sql)
            data = json.loads(
                df.to_json(orient="records", date_format="iso", date_unit="s")
            )
            return ChartResult(chart_type=parsed.name, sql=parsed.sql, data=data)
        except Exception as e:
            logger.error(f"Failed to execute chart SQL: {e}")
            return ChartResult(
                chart_type=parsed.name,
                sql=parsed.sql,
                data=[],
                error=str(e),
            )

    @classmethod
    def build_vis_chart(
        cls,
        chart_type: str,
        sql: str,
        data: list[dict[str, Any]],
        title: str = "",
        description: str = "",
    ) -> str:
        """Build a ```vis-chart JSON block for frontend rendering."""
        payload: dict[str, Any] = {
            "type": chart_type,
            "sql": sql,
            "data": data,
        }
        if title:
            payload["title"] = title
        if description:
            payload["describe"] = description

        return f"\n```vis-chart\n{json.dumps(payload, ensure_ascii=False, default=str)}\n```\n"

    @classmethod
    def build_error_block(cls, chart_type: str, sql: str, error: str) -> str:
        """Build an error display block when SQL execution fails."""
        return (
            f"\n> ⚠️ **Chart Error** ({chart_type}): {error}\n"
            f"> SQL: `{sql[:200]}{'...' if len(sql) > 200 else ''}`\n"
        )

    @classmethod
    def render(cls, text: str, reader: ExcelReader) -> str:
        """Full rendering pipeline for a single LLM response text.

        1. Parse all <api-call> blocks
        2. Execute each SQL via reader
        3. Replace api-call blocks with vis-chart or error blocks
        4. Return rendered text
        """
        parsed = cls.parse_api_calls(text)
        if not parsed:
            return text

        result_text = text
        for pc in parsed:
            chart = cls.execute_chart(pc, reader)
            if chart.error:
                block = cls.build_error_block(chart.chart_type, chart.sql, chart.error)
            else:
                block = cls.build_vis_chart(
                    chart_type=chart.chart_type,
                    sql=chart.sql,
                    data=chart.data,
                )

            # Replace the api-call block using a flexible regex
            # Match from <api-call> to </api-call>, using the name as anchor
            pattern = re.compile(
                r"<api-call>\s*<name>\s*"
                + re.escape(pc.name)
                + r"\s*</name>.*?</api-call>",
                re.DOTALL,
            )
            if pattern.search(result_text):
                result_text = pattern.sub(block.strip(), result_text, count=1)
            else:
                # Fallback: try looser pattern
                loose = re.compile(
                    r"<api-call>.*?" + re.escape(pc.name) + r".*?</api-call>",
                    re.DOTALL,
                )
                if loose.search(result_text):
                    result_text = loose.sub(block.strip(), result_text, count=1)
                else:
                    result_text += "\n" + block

        return result_text

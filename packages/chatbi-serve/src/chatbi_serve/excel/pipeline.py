"""ExcelAnalysisPipeline — Orchestrates the full Excel analysis workflow.

Two-phase flow:
1. prepare() — import file → LLM learns structure → transform table (column standardization)
2. analyze()  — user question → LLM generates SQL → execute via DuckDB → vis-chart output
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

from chatbi_core.schema.message import Message

from chatbi_serve.excel.api_call import ApiCall
from chatbi_serve.excel.prompts import (
    DISPLAY_TYPES_STR,
    LEARNING_PROMPT_EN,
    LEARNING_PROMPT_ZH,
    LEARNING_RESPONSE_FORMAT_EN,
    LEARNING_RESPONSE_FORMAT_ZH,
    LEARNING_USER_INPUT,
    LEARNING_USER_INPUT_EN,
    ANALYZE_PROMPT_EN,
    ANALYZE_PROMPT_ZH,
)
from chatbi_serve.excel.reader import ExcelReader, TransformedExcelResponse

if TYPE_CHECKING:
    from chatbi_core.model.base import BaseLLM

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    NEW = "new"
    IMPORTED = "imported"
    LEARNED = "learned"
    ERROR = "error"


@dataclass
class PrepareResult:
    data_analysis: str
    column_analysis: list[dict[str, str]]
    analysis_programs: list[str]


_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_OBJ_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> str:
    """Robust JSON extraction from LLM output (handles markdown code fences)."""
    # Try markdown code block first
    m = _JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    # Try raw JSON object
    m = _OBJ_RE.search(text)
    if m:
        return m.group(0).strip()
    return text.strip()


class ExcelAnalysisPipeline:
    """Orchestrates the Excel analysis two-phase workflow."""

    def __init__(
        self,
        llm: BaseLLM,
        file_path: str,
        file_name: Optional[str] = None,
        database: str = ":memory:",
        table_name: str = "data_analysis_table",
        language: str = "zh",
        emit_step: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ):
        self.llm = llm
        self.language = language
        self.state = PipelineState.NEW
        self.emit_step = emit_step

        self.reader = ExcelReader(
            file_path=file_path,
            file_name=file_name,
            database=database,
            table_name=table_name,
        )
        self.api_call = ApiCall()

        self._prepare_result: Optional[PrepareResult] = None

    def _emit_step(self, step_id: str, status: str, detail: Optional[str] = None) -> None:
        """Emit a pipeline step event if callback is configured."""
        if self.emit_step:
            self.emit_step(step_id, status, detail)

    # ── prepare: import + learn ──────────────────────────────────

    async def prepare(self) -> PrepareResult:
        """Import file into DuckDB, then have LLM analyze the structure and standardize columns."""
        logger.info(f"Preparing file: {self.reader.file_path}")

        # Step 1: Import (may already be done if db existed)
        if self.state == PipelineState.NEW:
            self._emit_step("store_file", "running")
            try:
                self.reader.import_file()
                self._emit_step("store_file", "completed")
            except Exception as e:
                self._emit_step("store_file", "failed", str(e))
                raise

            self._emit_step("create_duckdb", "running")
            try:
                self.state = PipelineState.IMPORTED
                self._emit_step("create_duckdb", "completed")
            except Exception as e:
                self._emit_step("create_duckdb", "failed", str(e))
                raise

        # Step 2: Collect metadata
        temp_table = self.reader.temp_table
        cols, sample = self.reader.get_sample_data(temp_table)
        schema = self.reader.get_create_table_sql(temp_table)
        summary = self.reader.get_summary(temp_table)

        # Format sample data: [col_names, row1, row2, ...]
        sample_rows = [list(cols)] + [list(row) for row in sample[:5]]
        data_example = json.dumps(sample_rows, ensure_ascii=False, default=str)

        # Step 3: Build learning prompt
        if self.language == "en":
            prompt_template = LEARNING_PROMPT_EN
            user_msg = LEARNING_USER_INPUT_EN
            response_format = json.dumps(LEARNING_RESPONSE_FORMAT_EN, ensure_ascii=False, indent=4)
        else:
            prompt_template = LEARNING_PROMPT_ZH
            user_msg = LEARNING_USER_INPUT
            response_format = json.dumps(LEARNING_RESPONSE_FORMAT_ZH, ensure_ascii=False, indent=4)

        system_prompt = prompt_template.format(
            data_example=data_example,
            data_summary=summary,
            table_schema=schema,
            response_format=response_format,
        )

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_msg),
        ]

        # Step 4: Call LLM for structure learning
        self._emit_step("learn_structure", "running")
        try:
            output = await self.llm.achat(messages)
            raw_text = output.text or ""
            self._emit_step("learn_structure", "completed", f"Generated {len(raw_text)} chars")
        except Exception as e:
            self._emit_step("learn_structure", "failed", str(e))
            raise

        # Step 5: Parse JSON response
        try:
            json_text = _extract_json(raw_text)
            parsed = json.loads(json_text)
            data_analysis = str(parsed.get("data_analysis", ""))
            column_analysis = parsed.get("column_analysis", [])
            analysis_programs = parsed.get("analysis_program", [])

            # Normalize column_analysis: ensure each entry is a dict with required keys
            normalized: list[dict[str, str]] = []
            for item in column_analysis:
                if isinstance(item, dict):
                    normalized.append({
                        "old_column_name": str(item.get("old_column_name", "")),
                        "new_column_name": str(item.get("new_column_name", "")),
                        "column_description": str(item.get("column_description", "")),
                    })
            column_analysis = normalized or [
                {"old_column_name": c, "new_column_name": c, "column_description": ""}
                for c in cols
            ]

            if isinstance(analysis_programs, str):
                analysis_programs = [analysis_programs]
            analysis_programs = [str(p) for p in analysis_programs]

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse learning JSON: {e}. Raw: {raw_text[:500]}")
            # Graceful fallback: use raw column names
            data_analysis = raw_text[:500]
            column_analysis = [
                {"old_column_name": c, "new_column_name": c, "column_description": ""}
                for c in cols
            ]
            analysis_programs = []

        # Step 6: Transform table (column standardization)
        self._emit_step("transform_columns", "running")
        try:
            transform = TransformedExcelResponse(
                description=data_analysis,
                columns=column_analysis,
                plans=analysis_programs,
            )
            self.reader.transform_table(temp_table, self.reader.table_name, transform)
            column_analysis = transform.columns
            self._emit_step("transform_columns", "completed", f"{len(column_analysis)} columns")
        except Exception as e:
            self._emit_step("transform_columns", "failed", str(e))
            raise

        self._prepare_result = PrepareResult(
            data_analysis=data_analysis,
            column_analysis=column_analysis,
            analysis_programs=analysis_programs,
        )
        self.state = PipelineState.LEARNED

        logger.info(
            f"Prepare complete: {len(column_analysis)} columns standardized → {self.reader.table_name}"
        )
        return self._prepare_result

    # ── analyze: question → SQL → vis-chart ─────────────────────

    async def analyze(
        self,
        question: str,
        chat_history: Optional[list[Message]] = None,
    ) -> str:
        """Answer a data question by generating and executing SQL, returning vis-chart output."""
        if self.state != PipelineState.LEARNED:
            await self.prepare()

        # Step: User question received
        self._emit_step("user_question", "running")
        self._emit_step("user_question", "completed", question[:50])

        tn = self.reader.table_name

        # Collect context
        schema = self.reader.get_create_table_sql(tn)
        cols, sample = self.reader.get_sample_data(tn)
        sample_rows = [list(cols)] + [list(row) for row in sample[:5]]
        data_example = json.dumps(sample_rows, ensure_ascii=False, default=str)

        # Build analyze prompt
        if self.language == "en":
            prompt_template = ANALYZE_PROMPT_EN
        else:
            prompt_template = ANALYZE_PROMPT_ZH

        system_prompt = prompt_template.format(
            table_schema=schema,
            data_example=data_example,
            table_name=tn,
            display_type=DISPLAY_TYPES_STR,
            user_input=question,
        )

        messages: list[Message] = [Message(role="system", content=system_prompt)]
        if chat_history:
            messages.extend(chat_history)
        messages.append(Message(role="user", content=question))

        # Step: Generate SQL
        self._emit_step("generate_sql", "running")
        try:
            output = await self.llm.achat(messages)
            raw_text = output.text or ""
            self._emit_step("generate_sql", "completed", f"{len(raw_text)} chars")
        except Exception as e:
            self._emit_step("generate_sql", "failed", str(e))
            raise

        # Step: Execute SQL and render visualization
        self._emit_step("execute_sql", "running")
        self._emit_step("render_visualization", "running")
        try:
            rendered = self.api_call.render(raw_text, self.reader)
            self._emit_step("execute_sql", "completed")
            self._emit_step("render_visualization", "completed")
            self._emit_step("return_frontend", "completed", "Success")
        except Exception as e:
            self._emit_step("execute_sql", "failed", str(e))
            self._emit_step("render_visualization", "failed", str(e))
            raise

        return rendered

    # ── convenience ──────────────────────────────────────────────

    @property
    def prepare_result(self) -> Optional[PrepareResult]:
        return self._prepare_result

    def close(self) -> None:
        self.reader.close()

    async def aclose(self) -> None:
        self.reader.close()

    def __enter__(self) -> ExcelAnalysisPipeline:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

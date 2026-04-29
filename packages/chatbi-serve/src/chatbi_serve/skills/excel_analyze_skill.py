"""ExcelAnalysisSkill — Invoke the full Excel analysis pipeline as a tool.

When the LLM calls this skill, the pipeline:
1. Imports the file into DuckDB
2. Learns column structure (standardizes names)
3. Generates and executes SQL for the user's question
4. Returns vis-chart protocol blocks for frontend rendering
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from chatbi_core.agent.skill.base import BaseSkill
from chatbi_core.model.base import BaseLLM
from chatbi_serve.excel.pipeline import ExcelAnalysisPipeline


class ExcelAnalysisSkill(BaseSkill):
    """Full Excel analysis: import → learn structure → generate SQL → return charts."""

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        emit_step: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ):
        self._llm = llm
        self._emit_step = emit_step
        self._pipelines: dict[str, ExcelAnalysisPipeline] = {}

    @property
    def name(self) -> str:
        return "excel_analyze"

    @property
    def description(self) -> str:
        return (
            "Analyze an uploaded Excel or CSV file by generating and executing DuckDB SQL queries. "
            "Returns interactive charts (vis-chart protocol). "
            "Use this when a user asks a data question about an uploaded file. "
            "The file must already be uploaded and the local file_path must be provided."
        )

    @property
    def description_cn(self) -> str:
        return (
            "分析已上传的Excel或CSV文件，通过生成并执行DuckDB SQL查询返回交互式图表（vis-chart协议）。"
            "当用户对已上传文件提出数据问题时使用此技能。文件需已上传并提供本地路径。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local path to the uploaded CSV or Excel file.",
                },
                "question": {
                    "type": "string",
                    "description": "The user's data analysis question.",
                },
            },
            "required": ["file_path", "question"],
        }

    def set_emit_step(self, callback: Callable[[str, str, Optional[str]], None]) -> None:
        """Set the emit_step callback for pipeline debug events."""
        self._emit_step = callback

    async def execute(
        self, file_path: str = "", question: str = "", **kwargs: Any
    ) -> str:
        if not file_path:
            return "No file_path provided."
        if not Path(file_path).exists():
            return f"File not found: {file_path}"
        if not question:
            return "No question provided."
        if not self._llm:
            return "LLM not available for Excel analysis."

        language = kwargs.get("language", "zh")

        # Cache pipeline per file_path to avoid re-learning on follow-up questions
        cache_key = file_path
        if cache_key not in self._pipelines:
            pipeline = ExcelAnalysisPipeline(
                llm=self._llm,
                file_path=file_path,
                database=":memory:",
                table_name="data_analysis_table",
                language=language,
                emit_step=self._emit_step,
            )
            self._pipelines[cache_key] = pipeline
        else:
            pipeline = self._pipelines[cache_key]
            # Update emit_step for subsequent calls (might be different stream)
            if self._emit_step:
                pipeline.emit_step = self._emit_step

        try:
            # Prepare if not yet learned
            result = await pipeline.prepare()

            # Analyze the question
            rendered = await pipeline.analyze(question)
            return rendered
        except Exception as e:
            return f"Excel analysis failed: {e}"

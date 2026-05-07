from __future__ import annotations

from aurora_core.agent.skill.base import SkillRegistry
from aurora_core.component import BaseService
from aurora_core.model.registry import ModelRegistry
from aurora_serve.datasource.service import DatasourceService


class SkillService(BaseService):
    name = "skill_service"

    def __init__(
        self,
        datasource_service: DatasourceService,
        model_registry: ModelRegistry,
        default_datasource: str = "",
    ):
        self.registry = SkillRegistry()
        self.datasource_service = datasource_service
        self.model_registry = model_registry
        self.default_datasource = default_datasource
        self.register_builtin_skills()

    def register_builtin_skills(self) -> None:
        from aurora_serve.skills.anomaly_detection_skill import AnomalyDetectionSkill
        from aurora_serve.skills.chart_skill import SQLChartSkill, SQLDashboardSkill
        from aurora_serve.skills.csv_skill import CSVAnalysisSkill
        from aurora_serve.skills.data_analysis_skill import DataAnalysisSkill
        from aurora_serve.skills.data_skills import (
            DatabaseSchemaSkill,
            PythonAnalysisSkill,
            SQLExecuteSkill,
        )
        from aurora_serve.skills.database_summary_skill import DatabaseSummarySkill
        from aurora_serve.skills.excel_analyze_skill import ExcelAnalysisSkill
        from aurora_serve.skills.excel_skill import Excel2TableSkill
        from aurora_serve.skills.indicator_skill import IndicatorSkill
        from aurora_serve.skills.metric_info_skill import MetricInfoSkill
        from aurora_serve.skills.report_skill import ReportSkill
        from aurora_serve.skills.volatility_analysis_skill import VolatilityAnalysisSkill
        from aurora_serve.skills.web_search_skill import WebSearchSkill

        default_llm = None
        try:
            default_llm = self.model_registry.get_llm()
        except RuntimeError:
            default_llm = None

        self.registry.register(CSVAnalysisSkill())
        self.registry.register(
            SQLExecuteSkill(
                datasource_service=self.datasource_service,
                datasource_name=self.default_datasource,
            )
        )
        self.registry.register(
            DatabaseSchemaSkill(
                datasource_service=self.datasource_service,
                datasource_name=self.default_datasource,
            )
        )
        self.registry.register(PythonAnalysisSkill())
        self.registry.register(WebSearchSkill())
        self.registry.register(
            Excel2TableSkill(
                datasource_service=self.datasource_service,
                datasource_name=self.default_datasource,
            )
        )
        self.registry.register(ExcelAnalysisSkill(llm=default_llm))
        self.registry.register(
            SQLChartSkill(
                llm=default_llm,
                datasource_service=self.datasource_service,
                datasource_name=self.default_datasource,
            )
        )
        self.registry.register(
            SQLDashboardSkill(
                llm=default_llm,
                datasource_service=self.datasource_service,
                datasource_name=self.default_datasource,
            )
        )
        self.registry.register(IndicatorSkill())
        self.registry.register(AnomalyDetectionSkill())
        self.registry.register(MetricInfoSkill())
        self.registry.register(VolatilityAnalysisSkill())
        self.registry.register(ReportSkill())
        self.registry.register(DataAnalysisSkill())
        self.registry.register(
            DatabaseSummarySkill(
                datasource_service=self.datasource_service,
                datasource_name=self.default_datasource,
            )
        )

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chatbi_serve.router import api_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from pathlib import Path

        from chatbi_core.agent.skill.base import SkillRegistry
        from chatbi_core.config.settings import Settings
        from chatbi_core.model.adapter.openai_adapter import OpenAILLM
        from chatbi_core.model.adapter.openai_embeddings import OpenAIEmbeddings
        from chatbi_core.model.registry import ModelRegistry
        from chatbi_core.schema.model import LLMConfig
        from chatbi_serve.agent.sql_agent import SQLAgent
        from chatbi_serve.chat.service import ChatService
        from chatbi_serve.datasource.schema import DBConfig
        from chatbi_serve.datasource.service import DatasourceService
        from chatbi_serve.skills.csv_skill import CSVAnalysisSkill
        from chatbi_serve.skills.chart_skill import SQLChartSkill, SQLDashboardSkill
        from chatbi_serve.skills.data_skills import (
            DatabaseSchemaSkill,
            PythonAnalysisSkill,
            SQLExecuteSkill,
        )
        from chatbi_serve.skills.excel_skill import Excel2TableSkill
        from chatbi_serve.skills.web_search_skill import WebSearchSkill

        config_path = Path("configs/chatbi.toml")
        if not config_path.exists():
            config_path = Path("../configs/chatbi.toml")

        settings = (
            Settings.from_toml(str(config_path))
            if config_path.exists()
            else Settings()
        )
        registry = ModelRegistry()
        for cfg in settings.llm_configs:
            if cfg.get("model_type") == "openai":
                api_key = cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning(
                        "Skipping LLM '%s': OPENAI_API_KEY not set",
                        cfg.get("model_name"),
                    )
                    continue
                llm_config = LLMConfig(**cfg)
                registry.register_llm(cfg["model_name"], OpenAILLM(llm_config))
                # Register embeddings with text-embedding-3-small by default
                emb_config = LLMConfig(
                    model_name="text-embedding-3-small",
                    model_type="openai",
                    api_key=api_key,
                    api_base=cfg.get("api_base"),
                )
                registry.register_embeddings("openai", OpenAIEmbeddings(emb_config))
        app.state.model_registry = registry

        datasource_service = DatasourceService()
        for ds_cfg in settings.datasource_configs:
            datasource_service.add_connection(DBConfig(**ds_cfg))
        app.state.datasource_service = datasource_service

        default_ds = settings.default_datasource if hasattr(settings, "default_datasource") else ""
        sql_agent = SQLAgent(registry, datasource_service, default_ds)

        skill_registry = SkillRegistry()
        skill_registry.register(CSVAnalysisSkill())
        skill_registry.register(
            SQLExecuteSkill(
                datasource_service=datasource_service,
                datasource_name=default_ds,
            )
        )
        skill_registry.register(
            DatabaseSchemaSkill(
                datasource_service=datasource_service,
                datasource_name=default_ds,
            )
        )
        skill_registry.register(PythonAnalysisSkill())
        skill_registry.register(WebSearchSkill())
        skill_registry.register(
            Excel2TableSkill(
                datasource_service=datasource_service,
                datasource_name=default_ds,
            )
        )
        try:
            default_llm = registry.get_llm()
        except RuntimeError:
            default_llm = None
        skill_registry.register(
            SQLChartSkill(
                llm=default_llm,
                datasource_service=datasource_service,
                datasource_name=default_ds,
            )
        )
        skill_registry.register(
            SQLDashboardSkill(
                llm=default_llm,
                datasource_service=datasource_service,
                datasource_name=default_ds,
            )
        )
        app.state.skill_registry = skill_registry

        app.state.chat_service = ChatService(registry, sql_agent, skill_registry)

        app.state.knowledge_stores = {}
        yield

    app = FastAPI(title="ChatBI", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app

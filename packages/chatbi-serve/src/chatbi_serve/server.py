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

        from chatbi_core.component import SystemApp
        from chatbi_core.config.settings import Settings
        from chatbi_core.model.adapter.anthropic_adapter import AnthropicLLM
        from chatbi_core.model.adapter.openai_adapter import OpenAILLM
        from chatbi_core.model.adapter.openai_embeddings import OpenAIEmbeddings
        from chatbi_core.model.registry import ModelRegistry
        from chatbi_core.schema.model import LLMConfig
        from chatbi_serve.apps.service import AppService
        from chatbi_serve.chat.service import ChatService
        from chatbi_serve.datasource.schema import DBConfig
        from chatbi_serve.datasource.service import DatasourceService
        from chatbi_serve.knowledge.service import KnowledgeService
        from chatbi_serve.metadata import MetadataStore
        from chatbi_serve.models.service import ModelConfigService
        from chatbi_serve.skills.service import SkillService

        config_path = Path("configs/chatbi.toml")
        if not config_path.exists():
            config_path = Path("../configs/chatbi.toml")

        settings = (
            Settings.from_toml(str(config_path))
            if config_path.exists()
            else Settings()
        )
        system_app = SystemApp(app)
        app.state.system_app = system_app

        metadata_store = MetadataStore()
        system_app.register_instance(metadata_store)
        app.state.metadata_store = metadata_store

        registry = ModelRegistry()
        for cfg in settings.llm_configs:
            model_type = cfg.get("model_type", "openai")
            if model_type == "openai":
                api_key = cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning(
                        "Skipping LLM '%s': OPENAI_API_KEY not set",
                        cfg.get("model_name"),
                    )
                    continue
                llm_config = LLMConfig(**cfg)
                registry.register_llm(cfg["model_name"], OpenAILLM(llm_config))
                emb_config = LLMConfig(
                    model_name="text-embedding-3-small",
                    model_type="openai",
                    api_key=api_key,
                    api_base=cfg.get("api_base"),
                )
                registry.register_embeddings("openai", OpenAIEmbeddings(emb_config))
            elif model_type == "anthropic":
                api_key = cfg.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.warning(
                        "Skipping LLM '%s': ANTHROPIC_API_KEY not set",
                        cfg.get("model_name"),
                    )
                    continue
                llm_config = LLMConfig(**cfg)
                registry.register_llm(cfg["model_name"], AnthropicLLM(llm_config))
        app.state.model_registry = registry
        model_config_service = ModelConfigService(metadata_store, registry)
        system_app.register_instance(model_config_service)

        datasource_service = DatasourceService(metadata_store)
        for ds_cfg in settings.datasource_configs:
            datasource_service.add_connection(DBConfig(**ds_cfg))
        system_app.register_instance(datasource_service)
        app.state.datasource_service = datasource_service

        default_ds = settings.default_datasource if hasattr(settings, "default_datasource") else ""

        skill_service = SkillService(datasource_service, registry, default_ds)
        system_app.register_instance(skill_service)
        skill_registry = skill_service.registry
        app.state.skill_registry = skill_registry

        knowledge_service = KnowledgeService(metadata_store, registry)
        system_app.register_instance(knowledge_service)
        app.state.knowledge_service = knowledge_service

        app_service = AppService(metadata_store)
        system_app.register_instance(app_service)
        app.state.app_service = app_service

        # Initialize MCP client
        from chatbi_core.mcp.client import MCPClient
        from chatbi_core.mcp.config import MCPConfig, MCPServerConfig

        mcp_client = MCPClient()
        try:
            mcp_config = MCPConfig.load()
            await mcp_client.connect_all(mcp_config.servers)
            logger.info(
                "MCP: %d servers connected, %d tools available",
                len(mcp_client._connections),
                len(mcp_client.get_tools()),
            )
        except Exception as e:
            logger.warning("MCP initialization failed: %s", e)
        app.state.mcp_client = mcp_client

        app.state.chat_service = ChatService(
            registry, skill_registry, mcp_client=mcp_client
        )
        system_app.register_instance(app.state.chat_service, name="chat_service")

        system_app.on_init()
        system_app.after_init()
        yield

        # Shutdown
        system_app.before_stop()
        mcp_client.disconnect_all()

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


# Create app instance for uvicorn
app = create_app()

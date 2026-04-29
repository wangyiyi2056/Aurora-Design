from __future__ import annotations

from uuid import uuid4

from chatbi_core.component import BaseService
from chatbi_core.model.adapter.anthropic_adapter import AnthropicLLM
from chatbi_core.model.adapter.openai_adapter import OpenAILLM
from chatbi_core.model.adapter.openai_embeddings import OpenAIEmbeddings
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.metadata import MetadataStore, ModelConfigEntity


class ModelConfigService(BaseService):
    name = "model_config_service"

    def __init__(self, metadata_store: MetadataStore, registry: ModelRegistry):
        self.metadata_store = metadata_store
        self.registry = registry

    def on_init(self) -> None:
        self.load_saved_models()

    def load_saved_models(self) -> None:
        with self.metadata_store.session() as session:
            for entity in session.query(ModelConfigEntity).all():
                self._register_runtime(entity)

    def list(self) -> list[ModelConfigEntity]:
        with self.metadata_store.session() as session:
            return list(session.query(ModelConfigEntity).order_by(ModelConfigEntity.created_at).all())

    def get(self, model_id: str) -> ModelConfigEntity:
        with self.metadata_store.session() as session:
            entity = session.get(ModelConfigEntity, model_id)
            if entity is None:
                raise KeyError(model_id)
            return entity

    def create(
        self,
        *,
        name: str,
        type: str = "llm",
        base_url: str = "",
        api_key: str = "",
        is_default: bool = False,
    ) -> ModelConfigEntity:
        with self.metadata_store.session() as session:
            if is_default:
                self._clear_default(session)
            entity = ModelConfigEntity(
                id=str(uuid4()),
                name=name,
                type=type,
                base_url=base_url,
                api_key=api_key,
                is_default=is_default,
            )
            session.add(entity)
            session.commit()
            self._register_runtime(entity)
            return entity

    def update(self, model_id: str, **updates) -> ModelConfigEntity:
        with self.metadata_store.session() as session:
            entity = session.get(ModelConfigEntity, model_id)
            if entity is None:
                raise KeyError(model_id)
            if updates.get("is_default") is True:
                self._clear_default(session)
            for field, value in updates.items():
                if value is not None and hasattr(entity, field):
                    setattr(entity, field, value)
            session.commit()
            self._register_runtime(entity)
            return entity

    def delete(self, model_id: str) -> bool:
        with self.metadata_store.session() as session:
            entity = session.get(ModelConfigEntity, model_id)
            if entity is None:
                return False
            session.delete(entity)
            session.commit()
            return True

    def set_test_status(
        self, model_id: str, success: bool, message: str | None = None
    ) -> ModelConfigEntity:
        return self.update(
            model_id,
            status="available" if success else "error",
            status_message=message,
        )

    def _clear_default(self, session) -> None:
        for entity in session.query(ModelConfigEntity).filter_by(is_default=True).all():
            entity.is_default = False

    def _register_runtime(self, entity: ModelConfigEntity) -> None:
        if not entity.api_key:
            return
        model_type = entity.type
        adapter_type = "anthropic" if model_type == "anthropic" else "openai"
        config = LLMConfig(
            model_name=entity.name,
            model_type=adapter_type,
            api_base=entity.base_url,
            api_key=entity.api_key,
        )
        if model_type == "embedding":
            self.registry.register_embeddings(entity.name, OpenAIEmbeddings(config))
            return
        if adapter_type == "anthropic":
            self.registry.register_llm(entity.name, AnthropicLLM(config))
        else:
            self.registry.register_llm(entity.name, OpenAILLM(config))


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"

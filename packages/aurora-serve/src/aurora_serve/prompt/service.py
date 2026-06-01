from __future__ import annotations

import re
from uuid import uuid4

from aurora_core.component import BaseService
from aurora_serve.metadata import MetadataStore, PromptTemplateEntity


class PromptTemplateService(BaseService):
    name = "prompt_template_service"
    SYSTEM_PROMPT_NAME = "global-system-prompt"

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    @staticmethod
    def _prompt_type(entity: PromptTemplateEntity) -> str:
        extra = entity.extra or {}
        value = extra.get("prompt_type")
        return value if value in {"system", "custom"} else "custom"

    def list(self, category: str | None = None) -> list[PromptTemplateEntity]:
        with self.metadata_store.session() as session:
            query = session.query(PromptTemplateEntity)
            if category:
                query = query.filter_by(category=category)
            return list(query.order_by(PromptTemplateEntity.updated_at.desc()).all())

    def list_custom(self) -> list[PromptTemplateEntity]:
        return [item for item in self.list() if self._prompt_type(item) == "custom"]

    def get_custom_enabled(self, prompt_ids: list[str]) -> list[PromptTemplateEntity]:
        if not prompt_ids:
            return []
        requested = list(dict.fromkeys(prompt_ids))
        with self.metadata_store.session() as session:
            items = (
                session.query(PromptTemplateEntity)
                .filter(PromptTemplateEntity.id.in_(requested))
                .filter_by(enabled=True)
                .all()
            )
            by_id = {
                item.id: item
                for item in items
                if self._prompt_type(item) == "custom"
            }
            return [by_id[prompt_id] for prompt_id in requested if prompt_id in by_id]

    def get_system_prompt(self) -> PromptTemplateEntity | None:
        with self.metadata_store.session() as session:
            items = (
                session.query(PromptTemplateEntity)
                .filter_by(name=self.SYSTEM_PROMPT_NAME)
                .all()
            )
            for item in items:
                if self._prompt_type(item) == "system":
                    return item
            return None

    def upsert_system_prompt(self, template: str) -> PromptTemplateEntity:
        with self.metadata_store.session() as session:
            items = (
                session.query(PromptTemplateEntity)
                .filter_by(name=self.SYSTEM_PROMPT_NAME)
                .all()
            )
            entity = next((item for item in items if self._prompt_type(item) == "system"), None)
            if entity is None:
                entity = PromptTemplateEntity(
                    id=str(uuid4()),
                    name=self.SYSTEM_PROMPT_NAME,
                    category="system",
                    template=template,
                    variables=[],
                    version=1,
                    enabled=True,
                    description="Global system prompt",
                    extra={"prompt_type": "system"},
                )
                session.add(entity)
            else:
                entity.template = template
                entity.enabled = True
                entity.extra = {**(entity.extra or {}), "prompt_type": "system"}
            session.commit()
            return entity

    def get(self, prompt_id: str) -> PromptTemplateEntity:
        with self.metadata_store.session() as session:
            entity = session.get(PromptTemplateEntity, prompt_id)
            if entity is None:
                raise KeyError(prompt_id)
            return entity

    def create(
        self,
        *,
        name: str,
        category: str = "general",
        template: str,
        variables: list[str] | None = None,
        version: int = 1,
        enabled: bool = True,
        description: str = "",
    ) -> PromptTemplateEntity:
        with self.metadata_store.session() as session:
            entity = PromptTemplateEntity(
                id=str(uuid4()),
                name=name,
                category=category,
                template=template,
                variables=variables or [],
                version=version,
                enabled=enabled,
                description=description,
                extra={"prompt_type": "custom"},
            )
            session.add(entity)
            session.commit()
            return entity

    def update(self, prompt_id: str, **updates) -> PromptTemplateEntity:
        with self.metadata_store.session() as session:
            entity = session.get(PromptTemplateEntity, prompt_id)
            if entity is None:
                raise KeyError(prompt_id)
            for field, value in updates.items():
                if value is not None and hasattr(entity, field):
                    setattr(entity, field, value)
            session.commit()
            return entity

    def delete(self, prompt_id: str) -> bool:
        with self.metadata_store.session() as session:
            entity = session.get(PromptTemplateEntity, prompt_id)
            if entity is None:
                return False
            session.delete(entity)
            session.commit()
            return True

    def render(self, prompt_id: str, variables: dict[str, object]) -> str:
        entity = self.get(prompt_id)
        required = {
            match.group(1).strip()
            for match in re.finditer(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}", entity.template)
        }
        missing = sorted(name for name in required if name not in variables)
        if missing:
            raise ValueError(f"Missing prompt variables: {', '.join(missing)}")

        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            if key not in variables:
                raise ValueError(f"Missing prompt variables: {key}")
            return str(variables[key])

        return re.sub(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}", replace, entity.template)

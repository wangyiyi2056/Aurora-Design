from __future__ import annotations

import re
from uuid import uuid4

from chatbi_core.component import BaseService
from chatbi_serve.metadata import MetadataStore, PromptTemplateEntity


class PromptTemplateService(BaseService):
    name = "prompt_template_service"

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    def list(self, category: str | None = None) -> list[PromptTemplateEntity]:
        with self.metadata_store.session() as session:
            query = session.query(PromptTemplateEntity)
            if category:
                query = query.filter_by(category=category)
            return list(query.order_by(PromptTemplateEntity.updated_at.desc()).all())

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

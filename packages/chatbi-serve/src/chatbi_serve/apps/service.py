from __future__ import annotations

from uuid import uuid4

from chatbi_core.component import BaseService
from chatbi_serve.metadata import AppEntity, MetadataStore


class AppService(BaseService):
    name = "app_service"

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    def list(self) -> list[AppEntity]:
        with self.metadata_store.session() as session:
            return list(session.query(AppEntity).order_by(AppEntity.created_at).all())

    def create(
        self,
        *,
        name: str,
        description: str = "",
        type: str = "chat",
        model: str = "",
        published: bool = False,
        knowledge_ids: list[str] | None = None,
        datasource_ids: list[str] | None = None,
        skill_names: list[str] | None = None,
    ) -> AppEntity:
        with self.metadata_store.session() as session:
            entity = AppEntity(
                id=str(uuid4()),
                name=name,
                description=description,
                type=type,
                model=model,
                published=published,
                knowledge_ids=knowledge_ids or [],
                datasource_ids=datasource_ids or [],
                skill_names=skill_names or [],
            )
            session.add(entity)
            session.commit()
            return entity

    def update(self, app_id: str, **updates) -> AppEntity:
        with self.metadata_store.session() as session:
            entity = session.get(AppEntity, app_id)
            if entity is None:
                raise KeyError(app_id)
            for field, value in updates.items():
                if value is not None and hasattr(entity, field):
                    setattr(entity, field, value)
            session.commit()
            return entity

    def delete(self, app_id: str) -> bool:
        with self.metadata_store.session() as session:
            entity = session.get(AppEntity, app_id)
            if entity is None:
                return False
            session.delete(entity)
            session.commit()
            return True

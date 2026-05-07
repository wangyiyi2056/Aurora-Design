from __future__ import annotations

from uuid import uuid4

from aurora_core.component import BaseService
from aurora_serve.metadata import MetadataStore, PluginEntity


class PluginService(BaseService):
    name = "plugin_service"

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    def list(self) -> list[PluginEntity]:
        with self.metadata_store.session() as session:
            return list(session.query(PluginEntity).order_by(PluginEntity.updated_at.desc()).all())

    def create(self, **payload) -> PluginEntity:
        with self.metadata_store.session() as session:
            entity = PluginEntity(id=str(uuid4()), **payload)
            session.add(entity)
            session.commit()
            return entity

    def get(self, plugin_id: str) -> PluginEntity:
        with self.metadata_store.session() as session:
            entity = session.get(PluginEntity, plugin_id)
            if entity is None:
                raise KeyError(plugin_id)
            return entity

    def update(self, plugin_id: str, **updates) -> PluginEntity:
        with self.metadata_store.session() as session:
            entity = session.get(PluginEntity, plugin_id)
            if entity is None:
                raise KeyError(plugin_id)
            for field, value in updates.items():
                if value is not None and hasattr(entity, field):
                    setattr(entity, field, value)
            session.commit()
            return entity

    def delete(self, plugin_id: str) -> bool:
        with self.metadata_store.session() as session:
            entity = session.get(PluginEntity, plugin_id)
            if entity is None:
                return False
            session.delete(entity)
            session.commit()
            return True

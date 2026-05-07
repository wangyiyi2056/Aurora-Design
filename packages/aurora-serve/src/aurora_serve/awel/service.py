from __future__ import annotations

from uuid import uuid4

from aurora_core.component import BaseService
from aurora_serve.metadata import FlowEntity, FlowRunEntity, MetadataStore


class FlowService(BaseService):
    name = "flow_service"

    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    def operators(self) -> list[dict]:
        return [
            {"name": "identity", "type": "map", "description": "Return input unchanged"},
            {"name": "uppercase", "type": "map", "description": "Uppercase string input"},
        ]

    def list(self) -> list[FlowEntity]:
        with self.metadata_store.session() as session:
            return list(session.query(FlowEntity).order_by(FlowEntity.updated_at.desc()).all())

    def create(self, **payload) -> FlowEntity:
        with self.metadata_store.session() as session:
            entity = FlowEntity(id=str(uuid4()), **payload)
            session.add(entity)
            session.commit()
            return entity

    def get(self, flow_id: str) -> FlowEntity:
        with self.metadata_store.session() as session:
            entity = session.get(FlowEntity, flow_id)
            if entity is None:
                raise KeyError(flow_id)
            return entity

    def update(self, flow_id: str, **updates) -> FlowEntity:
        with self.metadata_store.session() as session:
            entity = session.get(FlowEntity, flow_id)
            if entity is None:
                raise KeyError(flow_id)
            for field, value in updates.items():
                if value is not None and hasattr(entity, field):
                    setattr(entity, field, value)
            session.commit()
            return entity

    def delete(self, flow_id: str) -> bool:
        with self.metadata_store.session() as session:
            entity = session.get(FlowEntity, flow_id)
            if entity is None:
                return False
            for run in session.query(FlowRunEntity).filter_by(flow_id=flow_id).all():
                session.delete(run)
            session.delete(entity)
            session.commit()
            return True

    def run(self, flow_id: str, initial_input):
        entity = self.get(flow_id)
        try:
            output = self._execute_nodes(entity.nodes or [], initial_input)
            status = "completed"
            error = None
        except Exception as exc:
            output = None
            status = "failed"
            error = str(exc)
        with self.metadata_store.session() as session:
            run = FlowRunEntity(
                id=str(uuid4()),
                flow_id=flow_id,
                status=status,
                input=initial_input,
                output=output,
                error=error,
            )
            session.add(run)
            session.commit()
            return run

    def run_legacy(self, initial_input):
        return {"output": initial_input, "steps": [{"operator": "identity", "output": initial_input}]}

    def list_runs(self, flow_id: str) -> list[FlowRunEntity]:
        with self.metadata_store.session() as session:
            return list(
                session.query(FlowRunEntity)
                .filter_by(flow_id=flow_id)
                .order_by(FlowRunEntity.created_at.desc())
                .all()
            )

    def get_run(self, run_id: str) -> FlowRunEntity:
        with self.metadata_store.session() as session:
            entity = session.get(FlowRunEntity, run_id)
            if entity is None:
                raise KeyError(run_id)
            return entity

    def _execute_nodes(self, nodes: list[dict], initial_input):
        value = initial_input
        for node in nodes:
            node_type = node.get("type")
            if node_type == "identity":
                value = value
            elif node_type == "uppercase":
                value = str(value).upper()
            else:
                raise ValueError(f"Unsupported AWEL node type: {node_type}")
        return value

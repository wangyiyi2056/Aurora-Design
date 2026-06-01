"""Knowledge graph routes — entity / relationship CRUD and subgraph traversal.

All routes receive ``name: str`` as a path parameter.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from aurora_serve.knowledge.v2.schemas import (
    EntityCreateRequest,
    EntityMergeRequest,
    EntityUpdateRequest,
    GraphResponse,
    OperationSummaryResponse,
    RelationCreateRequest,
    RelationEditRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph"])


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


# ── Labels ───────────────────────────────────────────────────────────


@router.get("/graph/labels", response_model=List[str])
async def get_all_labels(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> List[str]:
    """Return all entity labels in the knowledge graph."""
    try:
        return await service.get_all_labels(name)
    except Exception as exc:
        logger.exception("Failed to get all labels")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/graph/labels/popular", response_model=List[str])
async def get_popular_labels(
    name: str,
    limit: int = Query(default=300, ge=1, le=5000, description="Maximum labels to return"),
    service: Any = Depends(get_knowledge_v2_service),
) -> List[str]:
    """Return the most-connected entity labels (ordered by degree)."""
    try:
        return await service.get_popular_labels(name, limit=limit)
    except Exception as exc:
        logger.exception("Failed to get popular labels")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/graph/labels/search", response_model=List[str])
async def search_labels(
    name: str,
    q: str = Query(..., min_length=1, description="Search query substring"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum results"),
    service: Any = Depends(get_knowledge_v2_service),
) -> List[str]:
    """Fuzzy-search entity labels by substring."""
    try:
        return await service.search_labels(name, query=q, limit=limit)
    except Exception as exc:
        logger.exception("Failed to search labels for '%s'", q)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Subgraph ─────────────────────────────────────────────────────────


@router.get("/graph/subgraph", response_model=GraphResponse)
async def get_subgraph(
    name: str,
    label: str = Query(..., min_length=1, description="Starting entity label"),
    max_depth: int = Query(default=3, ge=1, le=10, description="BFS traversal depth"),
    max_nodes: int = Query(default=1000, ge=1, le=10000, description="Maximum nodes to return"),
    service: Any = Depends(get_knowledge_v2_service),
) -> GraphResponse:
    """Retrieve a connected subgraph starting from the given label."""
    try:
        result = await service.get_subgraph(
            name, label=label, max_depth=max_depth, max_nodes=max_nodes
        )
        return GraphResponse(
            nodes=result.get("nodes", []),
            edges=result.get("edges", []),
        )
    except Exception as exc:
        logger.exception("Failed to get subgraph for label '%s'", label)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Entity Operations ────────────────────────────────────────────────


@router.get("/graph/entity/exists")
async def entity_exists(
    name: str,
    entity_name: str = Query(..., min_length=1, description="Entity name to check"),
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, bool]:
    """Check whether an entity exists in the knowledge graph."""
    try:
        exists = await service.entity_exists(name, entity_name=entity_name)
        return {"exists": exists}
    except Exception as exc:
        logger.exception("Failed to check entity existence for '%s'", entity_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph/entity/edit", response_model=OperationSummaryResponse)
async def edit_entity(
    name: str,
    req: EntityUpdateRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> OperationSummaryResponse:
    """Update an existing entity's properties."""
    try:
        result = await service.update_entity(
            name,
            entity_name=req.entity_name,
            updated_data=req.updated_data,
            allow_rename=req.allow_rename,
            allow_merge=req.allow_merge,
        )
        return OperationSummaryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to edit entity '%s'", req.entity_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph/entity/create", response_model=OperationSummaryResponse)
async def create_entity(
    name: str,
    req: EntityCreateRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> OperationSummaryResponse:
    """Create a new entity in the knowledge graph."""
    try:
        result = await service.create_entity(
            name,
            entity_name=req.entity_name,
            entity_type=req.entity_type,
            description=req.description,
            metadata=req.metadata,
        )
        return OperationSummaryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to create entity '%s'", req.entity_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/graph/entity/{entity_id}")
async def delete_entity(
    name: str,
    entity_id: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Delete an entity from the knowledge graph."""
    try:
        await service.delete_entity(name, entity_id)
        return {"deleted": True}
    except Exception as exc:
        logger.exception("Failed to delete entity '%s'", entity_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Relationship Operations ──────────────────────────────────────────


@router.post("/graph/relation/create", response_model=OperationSummaryResponse)
async def create_relation(
    name: str,
    req: RelationCreateRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> OperationSummaryResponse:
    """Create a new relationship between two entities."""
    try:
        result = await service.create_relation(
            name,
            source_entity=req.source_entity,
            target_entity=req.target_entity,
            relation_data=req.relation_data,
        )
        return OperationSummaryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Failed to create relation %s -> %s",
            req.source_entity,
            req.target_entity,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/graph/relation/edit", response_model=OperationSummaryResponse)
async def edit_relation(
    name: str,
    req: RelationEditRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> OperationSummaryResponse:
    """Update an existing relationship's properties."""
    try:
        result = await service.update_relation(
            name,
            source_entity=req.source_entity,
            target_entity=req.target_entity,
            updated_data=req.updated_data,
        )
        return OperationSummaryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Failed to edit relation %s -> %s",
            req.source_entity,
            req.target_entity,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/graph/relation")
async def delete_relation(
    name: str,
    source_id: str = Query(..., description="Source entity name"),
    target_id: str = Query(..., description="Target entity name"),
    service: Any = Depends(get_knowledge_v2_service),
) -> Dict[str, Any]:
    """Delete a relationship from the knowledge graph."""
    try:
        await service.delete_relation(name, source_id, target_id)
        return {"deleted": True}
    except Exception as exc:
        logger.exception("Failed to delete relation %s -> %s", source_id, target_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Entity Merge ─────────────────────────────────────────────────────


@router.post("/graph/entities/merge", response_model=OperationSummaryResponse)
async def merge_entities(
    name: str,
    req: EntityMergeRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> OperationSummaryResponse:
    """Merge multiple entities into a single target entity."""
    try:
        result = await service.merge_entities(
            name,
            entities_to_change=req.entities_to_change,
            entity_to_change_into=req.entity_to_change_into,
        )
        return OperationSummaryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Failed to merge entities %s into %s",
            req.entities_to_change,
            req.entity_to_change_into,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

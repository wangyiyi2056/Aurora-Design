"""Cache management routes — statistics and selective clearing.

Endpoints for monitoring cache performance and clearing caches
by query mode or specific document IDs.

All routes receive ``name: str`` as a path parameter (from the
``/knowledge/{name}`` prefix applied at registration time).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cache"])


def get_knowledge_v2_service(request: Request) -> Any:
    """Resolve the KnowledgeV2Service from the system app registry."""
    from aurora_serve.knowledge.v2.service import KnowledgeV2Service

    return request.app.state.system_app.get_component(
        "knowledge_v2_service", KnowledgeV2Service
    )


# ── Request/Response Schemas ────────────────────────────────────────


class ClearCacheRequest(BaseModel):
    """Request body for clearing caches."""

    mode: str = Field(
        default="all",
        description="Query mode for selective clearing: mix, hybrid, local, global, naive, all",
    )
    document_ids: Optional[list[str]] = Field(
        default=None,
        description="Specific document IDs to clear from entity cache",
    )


class CacheStatsLayerResponse(BaseModel):
    """Statistics for a single cache layer."""

    hits: int
    misses: int
    evictions: int
    size: int
    memory_bytes: int
    hit_rate: float


class CacheStatsResponse(BaseModel):
    """Response body for cache statistics."""

    layers: dict[str, CacheStatsLayerResponse]
    aggregate: dict[str, Any]
    config: dict[str, Any]


class ClearCacheResponse(BaseModel):
    """Response body for cache clearing operations."""

    cleared: dict[str, int]
    total_cleared: int
    message: str


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> CacheStatsResponse:
    """Get cache statistics for a knowledge base.

    Returns per-layer and aggregate statistics for all cache layers
    including LLM response cache, entity extraction cache, and
    embedding similarity cache.

    Args:
        name: Knowledge base name.

    Returns:
        Cache statistics with per-layer details and aggregate totals.
    """
    try:
        # Get or create cache manager for this knowledge base
        cache_manager = await _get_cache_manager(service, name)

        # Collect statistics
        stats = await cache_manager.get_stats()
        config_summary = cache_manager.get_config_summary()

        return CacheStatsResponse(
            layers={
                "llm": CacheStatsLayerResponse(**stats.llm.to_dict()),
                "entity": CacheStatsLayerResponse(**stats.entity.to_dict()),
                "embedding": CacheStatsLayerResponse(**stats.embedding.to_dict()),
            },
            aggregate=stats.to_dict()["aggregate"],
            config=config_summary,
        )
    except Exception as e:
        logger.error("Failed to get cache stats for %s: %s", name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear", response_model=ClearCacheResponse)
async def clear_cache(
    name: str,
    request: ClearCacheRequest,
    service: Any = Depends(get_knowledge_v2_service),
) -> ClearCacheResponse:
    """Clear caches for a knowledge base.

    Supports selective clearing based on query mode or specific
    document IDs.

    Query mode determines which caches to clear:
    - ``all`` or ``mix``: All cache layers
    - ``hybrid`` or ``global``: LLM + entity caches
    - ``local``: Entity + embedding caches
    - ``naive``: Embedding cache only

    If ``document_ids`` is provided, only entity cache entries
    for those documents are cleared.

    Args:
        name: Knowledge base name.
        request: Clear cache request with mode and optional document IDs.

    Returns:
        Summary of cleared entries per cache layer.
    """
    try:
        cache_manager = await _get_cache_manager(service, name)

        # Handle document-specific clearing
        if request.document_ids:
            cleared_count = await cache_manager.clear_by_document_ids(
                request.document_ids
            )
            return ClearCacheResponse(
                cleared={"entity": cleared_count},
                total_cleared=cleared_count,
                message=f"Cleared {cleared_count} entity cache entries for specified documents",
            )

        # Handle mode-based clearing
        valid_modes = {"mix", "hybrid", "local", "global", "naive", "all"}
        if request.mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {request.mode}. Must be one of: {', '.join(sorted(valid_modes))}",
            )

        cleared = await cache_manager.clear_by_mode(request.mode)
        total = sum(cleared.values())

        return ClearCacheResponse(
            cleared=cleared,
            total_cleared=total,
            message=f"Cleared {total} cache entries using mode '{request.mode}'",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to clear cache for %s: %s", name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/cleanup", response_model=dict[str, Any])
async def cleanup_expired_cache(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> dict[str, Any]:
    """Remove expired entries from all cache layers.

    This is a maintenance operation that removes entries that have
    exceeded their TTL. It does not affect the cache size limits.

    Args:
        name: Knowledge base name.

    Returns:
        Summary of cleaned entries per cache layer.
    """
    try:
        cache_manager = await _get_cache_manager(service, name)
        cleaned = await cache_manager.cleanup_expired()
        total = sum(cleaned.values())

        return {
            "cleaned": cleaned,
            "total_cleaned": total,
            "message": f"Cleaned up {total} expired cache entries",
        }
    except Exception as e:
        logger.error("Failed to cleanup cache for %s: %s", name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/config")
async def get_cache_config(
    name: str,
    service: Any = Depends(get_knowledge_v2_service),
) -> dict[str, Any]:
    """Get cache configuration for a knowledge base.

    Returns the current cache configuration including enabled status,
    TTL settings, and size limits for each cache layer.

    Args:
        name: Knowledge base name.

    Returns:
        Current cache configuration.
    """
    try:
        cache_manager = await _get_cache_manager(service, name)
        return cache_manager.get_config_summary()
    except Exception as e:
        logger.error("Failed to get cache config for %s: %s", name, e)
        raise HTTPException(status_code=500, detail=str(e))


async def _get_cache_manager(service: Any, name: str) -> Any:
    """Get or create a cache manager for a knowledge base.

    Args:
        service: The KnowledgeV2Service instance.
        name: Knowledge base name.

    Returns:
        CacheManager instance for the knowledge base.
    """
    from aurora_ext.rag.cache import CacheManager, CacheConfig

    # Try to get existing cache manager from service
    if hasattr(service, "_cache_managers") and name in service._cache_managers:
        return service._cache_managers[name]

    # Create new cache manager with default config
    # In production, this would load from the knowledge base's config
    config = CacheConfig()

    # Get working directory from service
    working_dir = "./rag_storage"
    if hasattr(service, "working_dir"):
        working_dir = service.working_dir

    cache_manager = CacheManager(config=config, working_dir=working_dir)

    # Store in service for reuse
    if not hasattr(service, "_cache_managers"):
        service._cache_managers = {}
    service._cache_managers[name] = cache_manager

    return cache_manager

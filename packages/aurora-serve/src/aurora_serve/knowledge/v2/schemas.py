"""Pydantic v2 request / response schemas for the Knowledge V2 API.

Migrated from LightRAG API schemas and adapted to the Aurora type system.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────


class QueryMode(str, Enum):
    """Supported RAG retrieval modes."""

    LOCAL = "local"
    GLOBAL = "global"
    HYBRID = "hybrid"
    NAIVE = "naive"
    MIX = "mix"
    BYPASS = "bypass"


class DocStatusEnum(str, Enum):
    """Document processing lifecycle states."""

    PENDING = "PENDING"
    PARSING = "PARSING"
    ANALYZING = "ANALYZING"
    PREPROCESSED = "PREPROCESSED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class InsertStatusEnum(str, Enum):
    """Insert operation result states."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


class ScanStatusEnum(str, Enum):
    """Scan operation result states."""

    SCANNING_STARTED = "scanning_started"
    SCANNING_SKIPPED_PIPELINE_BUSY = "scanning_skipped_pipeline_busy"


# ── Query Models ─────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """RAG query request with all retrieval parameters."""

    query: str = Field(..., min_length=3, description="Query text (minimum 3 characters)")
    mode: QueryMode = Field(
        default=QueryMode.MIX,
        description="Retrieval mode: local|global|hybrid|naive|mix|bypass",
    )
    only_need_context: bool = Field(
        default=False, description="Return only retrieved context without LLM generation"
    )
    only_need_prompt: bool = Field(
        default=False, description="Return only the assembled prompt without LLM generation"
    )
    response_type: str = Field(
        default="Multiple Paragraphs", description="Desired response format"
    )
    top_k: int = Field(default=40, description="Top-k entities/relations to retrieve")
    chunk_top_k: int = Field(default=20, description="Top-k chunks to retrieve")
    max_entity_tokens: int = Field(default=6000, description="Token budget for entities")
    max_relation_tokens: int = Field(default=8000, description="Token budget for relations")
    max_total_tokens: int = Field(default=30000, description="Total token budget")
    hl_keywords: List[str] = Field(
        default_factory=list, description="Pre-supplied high-level keywords"
    )
    ll_keywords: List[str] = Field(
        default_factory=list, description="Pre-supplied low-level keywords"
    )
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list, description="Prior conversation turns for context"
    )
    user_prompt: Optional[str] = Field(
        default=None, description="Additional user prompt to inject"
    )
    enable_rerank: bool = Field(
        default=False, description="Enable reranking of retrieved chunks"
    )
    include_references: bool = Field(
        default=True, description="Include source references in response"
    )
    include_chunk_content: bool = Field(
        default=False, description="Include raw chunk content in response"
    )
    stream: bool = Field(default=True, description="Stream the response")


class QueryResponse(BaseModel):
    """Non-streaming RAG query response."""

    response: str = Field(..., description="Generated response text")
    references: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Source references"
    )


class QueryDataResponse(BaseModel):
    """Structured data retrieval response with entities, relationships, and chunks."""

    status: str = Field(default="success", description="Response status")
    message: str = Field(default="", description="Status message")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Retrieved data: entities, relationships, chunks, references",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Query metadata: query_mode, keywords, processing_info",
    )


# ── Document Models ──────────────────────────────────────────────────


class InsertTextRequest(BaseModel):
    """Request to insert a single text document."""

    text: str = Field(..., min_length=1, description="Text content to insert")
    file_source: Optional[str] = Field(
        default=None, description="Optional file source identifier"
    )


class InsertTextsRequest(BaseModel):
    """Request to batch-insert multiple text documents."""

    texts: List[str] = Field(..., min_length=1, description="Text contents to insert")
    file_sources: Optional[List[str]] = Field(
        default=None, description="Optional file source identifiers"
    )


class InsertResponse(BaseModel):
    """Response from a document insert operation."""

    status: InsertStatusEnum = Field(..., description="Operation status")
    message: str = Field(default="", description="Status message")
    track_id: str = Field(default="", description="Tracking ID for this insert batch")


class ScanResponse(BaseModel):
    """Response from a directory scan operation."""

    status: ScanStatusEnum = Field(..., description="Scan status")
    message: str = Field(default="", description="Status message")
    track_id: str = Field(default="", description="Tracking ID for this scan")


class DocumentsRequest(BaseModel):
    """Paginated document listing request."""

    status_filter: Optional[DocStatusEnum] = Field(
        default=None, description="Filter by single status (deprecated, use status_filters)"
    )
    status_filters: List[DocStatusEnum] = Field(
        default_factory=list, description="Filter by multiple statuses"
    )
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(
        default=50, ge=10, le=200, description="Number of results per page"
    )
    sort_field: str = Field(default="created_at", description="Field to sort by")
    sort_direction: str = Field(
        default="desc", description="Sort direction: asc or desc"
    )


class DocStatusResponse(BaseModel):
    """Single document processing status record."""

    id: str = Field(..., description="Document ID")
    content_summary: str = Field(default="", description="Content preview/summary")
    content_length: int = Field(default=0, description="Content length in characters")
    status: str = Field(..., description="Current processing status")
    created_at: str = Field(default="", description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(default="", description="Last update timestamp (ISO 8601)")
    track_id: str = Field(default="", description="Batch tracking ID")
    chunks_count: int = Field(default=0, description="Number of chunks produced")
    error_msg: Optional[str] = Field(default=None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    file_path: str = Field(default="", description="Source file path")


class DeleteDocRequest(BaseModel):
    """Request to delete one or more documents."""

    doc_ids: List[str] = Field(..., description="Document IDs to delete")
    delete_file: bool = Field(
        default=False, description="Also delete the source file from disk"
    )
    delete_llm_cache: bool = Field(
        default=False, description="Also delete associated LLM cache entries"
    )
    force: bool = Field(
        default=False,
        description="Force delete even if document is being processed (caller should cancel pipeline first)",
    )


class PipelineStatusResponse(BaseModel):
    """Current state of the document ingestion pipeline."""

    autoscanned: bool = Field(default=False, description="Whether auto-scanning is active")
    busy: bool = Field(default=False, description="Whether the pipeline is currently busy")
    job_name: str = Field(default="", description="Current job name")
    job_start: str = Field(default="", description="Job start timestamp (ISO 8601)")
    docs: Dict[str, Any] = Field(
        default_factory=dict, description="Document counts: total, processed, failed, pending"
    )
    stages: Dict[str, int] = Field(
        default_factory=dict, description="Active worker counts per stage: parsing, processing"
    )
    batchs: Dict[str, Any] = Field(
        default_factory=dict, description="Batch counts: total, current"
    )
    cur_batch: int = Field(default=0, description="Current batch index")
    request_pending: bool = Field(
        default=False, description="Whether new documents are pending pickup"
    )
    latest_message: str = Field(default="", description="Latest pipeline message")
    history_messages: List[str] = Field(
        default_factory=list, description="Recent pipeline history"
    )
    update_status: str = Field(
        default="idle", description="Pipeline status: processing or idle"
    )


class StatusCountsResponse(BaseModel):
    """Document counts grouped by processing status."""

    counts: Dict[str, int] = Field(
        default_factory=dict, description="Mapping of status name to document count"
    )


# ── Graph Models ─────────────────────────────────────────────────────


class EntityUpdateRequest(BaseModel):
    """Request to update an existing entity."""

    entity_name: str = Field(..., description="Current entity name")
    updated_data: Dict[str, Any] = Field(..., description="Fields to update")
    allow_rename: bool = Field(
        default=False, description="Allow renaming the entity via entity_name in updated_data"
    )
    allow_merge: bool = Field(
        default=False, description="Allow merging if rename conflicts with existing entity"
    )


class EntityCreateRequest(BaseModel):
    """Request to create a new entity."""

    entity_name: str = Field(..., description="Entity name")
    entity_type: str = Field(default="", description="Entity type/category")
    description: str = Field(default="", description="Entity description")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional entity metadata"
    )


class RelationCreateRequest(BaseModel):
    """Request to create a new relationship."""

    source_entity: str = Field(..., description="Source entity name")
    target_entity: str = Field(..., description="Target entity name")
    relation_data: Dict[str, Any] = Field(
        default_factory=dict, description="Relationship properties"
    )


class RelationEditRequest(BaseModel):
    """Request to update an existing relationship."""

    source_entity: str = Field(..., description="Source entity name")
    target_entity: str = Field(..., description="Target entity name")
    updated_data: Dict[str, Any] = Field(..., description="Fields to update")


class EntityMergeRequest(BaseModel):
    """Request to merge multiple entities into one."""

    entities_to_change: List[str] = Field(
        ..., min_length=1, description="Entity names to merge away"
    )
    entity_to_change_into: str = Field(
        ..., description="Target entity to merge into"
    )


class GraphResponse(BaseModel):
    """Subgraph response with nodes and edges."""

    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Graph nodes")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="Graph edges")


class OperationSummaryResponse(BaseModel):
    """Response summarizing a graph mutation operation."""

    merged: bool = Field(default=False, description="Whether a merge was performed")
    merge_status: str = Field(default="", description="Merge operation status")
    operation_status: str = Field(default="", description="Overall operation status")
    renamed: bool = Field(default=False, description="Whether an entity was renamed")
    final_entity: str = Field(default="", description="Final entity name after operation")
    target_entity: Optional[str] = Field(
        default=None, description="Target entity name if applicable"
    )


# ── Ollama Compatibility Models ──────────────────────────────────────


class OllamaMessage(BaseModel):
    """Single message in an Ollama conversation."""

    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class OllamaChatRequest(BaseModel):
    """Ollama-compatible chat request."""

    model: str = Field(default="lightrag", description="Model name")
    messages: List[OllamaMessage] = Field(..., description="Conversation messages")
    stream: bool = Field(default=True, description="Stream the response")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Model options/parameters"
    )
    system: Optional[str] = Field(
        default=None, description="System prompt override"
    )


class OllamaGenerateRequest(BaseModel):
    """Ollama-compatible text generation request."""

    model: str = Field(default="lightrag", description="Model name")
    prompt: str = Field(..., description="Generation prompt")
    system: Optional[str] = Field(
        default=None, description="System prompt override"
    )
    stream: bool = Field(default=False, description="Stream the response")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Model options/parameters"
    )

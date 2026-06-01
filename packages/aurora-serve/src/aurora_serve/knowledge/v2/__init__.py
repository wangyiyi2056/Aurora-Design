"""Phase 5 — Knowledge V2 API layer.

RAG knowledge base API endpoints migrated from LightRAG, including:
- Document ingestion and pipeline management
- Multi-mode RAG queries (local / global / hybrid / naive / mix / bypass)
- Knowledge graph CRUD operations
- Ollama-compatible API shim
"""

from aurora_serve.knowledge.v2.schemas import (
    DeleteDocRequest,
    DocStatusResponse,
    DocumentsRequest,
    EntityCreateRequest,
    EntityMergeRequest,
    EntityUpdateRequest,
    GraphResponse,
    InsertResponse,
    InsertTextRequest,
    InsertTextsRequest,
    OllamaChatRequest,
    OllamaGenerateRequest,
    OllamaMessage,
    OperationSummaryResponse,
    PipelineStatusResponse,
    QueryDataResponse,
    QueryRequest,
    QueryResponse,
    RelationCreateRequest,
    RelationEditRequest,
    ScanResponse,
    StatusCountsResponse,
)

__all__ = [
    "DeleteDocRequest",
    "DocStatusResponse",
    "DocumentsRequest",
    "EntityCreateRequest",
    "EntityMergeRequest",
    "EntityUpdateRequest",
    "GraphResponse",
    "InsertResponse",
    "InsertTextRequest",
    "InsertTextsRequest",
    "OllamaChatRequest",
    "OllamaGenerateRequest",
    "OllamaMessage",
    "OperationSummaryResponse",
    "PipelineStatusResponse",
    "QueryDataResponse",
    "QueryRequest",
    "QueryResponse",
    "RelationCreateRequest",
    "RelationEditRequest",
    "ScanResponse",
    "StatusCountsResponse",
]

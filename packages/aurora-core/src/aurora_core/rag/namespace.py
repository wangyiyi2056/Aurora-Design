"""Storage namespace constants for organizing data across storage backends.

Migrated from LightRAG ``namespace.py``.
"""


class NameSpace:
    """Logical namespace identifiers used by the RAG storage layer.

    Each namespace maps to a collection / table / directory inside a
    concrete storage backend (KV, Vector, Graph, DocStatus).
    """

    # ── KV Store namespaces ──────────────────────────────────────
    KV_STORE_FULL_DOCS: str = "full_docs"
    KV_STORE_TEXT_CHUNKS: str = "text_chunks"
    KV_STORE_LLM_RESPONSE_CACHE: str = "llm_response_cache"
    KV_STORE_FULL_ENTITIES: str = "full_entities"
    KV_STORE_FULL_RELATIONS: str = "full_relations"
    KV_STORE_ENTITY_CHUNKS: str = "entity_chunks"
    KV_STORE_RELATION_CHUNKS: str = "relation_chunks"

    # ── Vector Store namespaces ──────────────────────────────────
    VECTOR_STORE_ENTITIES: str = "entities"
    VECTOR_STORE_RELATIONSHIPS: str = "relationships"
    VECTOR_STORE_CHUNKS: str = "chunks"

    # ── Graph Store namespaces ───────────────────────────────────
    GRAPH_STORE_CHUNK_ENTITY_RELATION: str = "chunk_entity_relation"

    # ── Doc Status namespaces ────────────────────────────────────
    DOC_STATUS: str = "doc_status"

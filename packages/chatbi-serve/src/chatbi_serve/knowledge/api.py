import os
import tempfile
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Request, UploadFile

from chatbi_core.model.registry import ModelRegistry
from chatbi_ext.rag import (
    ChunkManager,
    ChunkParameters,
    EmbeddingAssembler,
    EmbeddingRetriever,
    KnowledgeFactory,
)
from chatbi_ext.storage import ChromaVectorStore

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def get_knowledge_stores(request: Request) -> Dict[str, Any]:
    stores = getattr(request.app.state, "knowledge_stores", None)
    if stores is None:
        stores = {}
        request.app.state.knowledge_stores = stores
    return stores


def get_model_registry(request: Request) -> ModelRegistry:
    return request.app.state.model_registry


@router.post("/upload")
async def upload_knowledge(
    name: str,
    file: UploadFile = File(...),
    stores: Dict[str, Any] = Depends(get_knowledge_stores),
    registry: ModelRegistry = Depends(get_model_registry),
) -> Dict[str, str]:
    suffix = os.path.splitext(file.filename or "")[1] or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    knowledge = KnowledgeFactory.from_file_path(tmp_path)
    chunk_manager = ChunkManager(ChunkParameters(chunk_size=500, chunk_overlap=50))

    # Use OpenAI embedding if available, otherwise raise
    embeddings = registry.get_embeddings()
    vector_store = ChromaVectorStore(collection_name=name)
    assembler = EmbeddingAssembler(
        knowledge=knowledge,
        chunk_manager=chunk_manager,
        embeddings=embeddings,
        vector_store=vector_store,
    )
    ids = assembler.persist()
    stores[name] = assembler.as_retriever(top_k=5)

    os.unlink(tmp_path)
    return {"name": name, "chunks": len(ids)}


@router.get("")
async def list_knowledge(
    stores: Dict[str, Any] = Depends(get_knowledge_stores),
) -> List[str]:
    return list(stores.keys())


@router.post("/{name}/query")
async def query_knowledge(
    name: str,
    query: str,
    stores: Dict[str, Any] = Depends(get_knowledge_stores),
) -> Dict[str, Any]:
    if name not in stores:
        return {"error": f"Knowledge base '{name}' not found"}
    retriever = stores[name]
    docs = await retriever.retrieve(query)
    return {
        "results": [
            {"content": d.content, "metadata": d.metadata} for d in docs
        ]
    }

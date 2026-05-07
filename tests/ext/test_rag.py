import pytest

from aurora_ext.rag import (
    ChunkManager,
    ChunkParameters,
    EmbeddingAssembler,
    KnowledgeFactory,
)
from aurora_ext.rag.knowledge.base import Document
from aurora_ext.rag.retriever.bm25_retriever import BM25Retriever
from aurora_ext.storage.chroma_store import ChromaVectorStore


class FakeEmbeddings:
    async def aembed(self, texts):
        # Return 384-dim vectors to match default ChromaDB embedding dimension
        return [[1.0] + [0.0] * 383 for _ in texts]


class FakeKnowledge:
    def load(self):
        return [
            Document(
                content="Aurora is an agentic AI data platform.", metadata={"src": "doc1"}
            ),
            Document(
                content="It supports SQL generation and RAG.", metadata={"src": "doc2"}
            ),
        ]


def test_chunk_manager():
    cm = ChunkManager(ChunkParameters(chunk_size=20, chunk_overlap=5))
    docs = [Document(content="Hello world this is a long document.", metadata={})]
    chunks = cm.split(docs)
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_bm25_retriever():
    docs = [
        Document(content="Aurora supports SQL", metadata={}),
        Document(content="Aurora supports RAG", metadata={}),
    ]
    retriever = BM25Retriever(docs, top_k=2)
    results = await retriever.retrieve("RAG")
    assert len(results) == 2
    assert "RAG" in results[0].content


@pytest.mark.asyncio
async def test_embedding_assembler_and_retriever():
    knowledge = FakeKnowledge()
    chunk_manager = ChunkManager(ChunkParameters(chunk_size=100, chunk_overlap=10))
    embeddings = FakeEmbeddings()
    store = ChromaVectorStore(collection_name="test-rag")
    assembler = EmbeddingAssembler(
        knowledge=knowledge,
        chunk_manager=chunk_manager,
        embeddings=embeddings,
        vector_store=store,
    )
    ids = assembler.persist()
    assert len(ids) > 0

    retriever = assembler.as_retriever(top_k=2)
    results = await retriever.retrieve("agentic AI")
    assert len(results) <= 2

import pytest

from aurora_ext.rag.retrieval.query_engine import QueryEngine, QueryMode, QueryParam


class FakeLLM:
    async def achat(self, messages, **kwargs):
        raise AssertionError("LLM should not be called for context-only retrieval")

    async def achat_stream(self, messages, **kwargs):
        raise AssertionError("LLM should not be called for context-only retrieval")
        yield


class FakeVectorStorage:
    async def query(
        self,
        query: str,
        top_k: int,
        cosine_threshold: float = 0.0,
        where: dict | None = None,
    ):
        kind = (where or {}).get("kind")
        if kind == "entity":
            return [
                {
                    "id": "kb:entity:wrong",
                    "entity_name": "kb:entity:wrong",
                    "description": "A misleading entity hit.",
                    "score": 0.9,
                    "kind": "entity",
                }
            ]
        if kind == "relation":
            return []
        if kind == "chunk":
            return [
                {
                    "id": "kb:chunk:right:0",
                    "content": "The correct answer is in the vector chunk.",
                    "file_path": "right.md",
                    "score": 0.95,
                    "kind": "chunk",
                }
            ]
        return []


class FakeKVStorage:
    async def get_by_ids(self, keys: list[str]):
        records = {
            "kb:text_chunks:wrong:0": {
                "id": "kb:text_chunks:wrong:0",
                "content": "This KG-associated chunk is not the answer.",
                "file_path": "wrong.md",
            }
        }
        return [records.get(key) for key in keys]


class FakeGraphStorage:
    async def search_labels(self, query: str, limit: int = 50):
        return ["kb:entity:wrong"]

    async def get_node(self, node_id: str):
        if node_id == "kb:entity:wrong":
            return {
                "id": node_id,
                "entity_name": node_id,
                "entity_type": "Concept",
                "description": "A graph hit tied to a different file.",
                "source_id": "kb:text_chunks:wrong:0",
            }
        return None

    async def get_node_edges(self, node_id: str):
        return []


@pytest.mark.asyncio
async def test_mix_retrieval_keeps_naive_vector_chunks_from_other_files():
    engine = QueryEngine(
        llm=FakeLLM(),
        embedding_func=None,
        kv_storage=FakeKVStorage(),
        vector_storage=FakeVectorStorage(),
        graph_storage=FakeGraphStorage(),
    )

    result = await engine.query(
        QueryParam(
            query="where is the correct answer?",
            kb_name="kb",
            mode=QueryMode.MIX,
            only_need_context=True,
            hl_keywords=[],
            ll_keywords=["wrong"],
            top_k=5,
            chunk_top_k=5,
        )
    )

    chunk_paths = [chunk.get("file_path") for chunk in result.chunks]

    assert "right.md" in chunk_paths

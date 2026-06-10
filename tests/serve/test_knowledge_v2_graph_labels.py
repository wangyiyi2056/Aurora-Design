import pytest

from aurora_core.model.base import BaseLLM
from aurora_core.model.registry import ModelRegistry
from aurora_core.schema.message import ModelOutput
from aurora_core.schema.model import LLMConfig
from aurora_ext.rag.retrieval.query_engine import QueryParam
from aurora_serve.knowledge.v2.service import KnowledgeV2Service


class FakeLLM(BaseLLM):
    async def achat(self, messages, **kwargs):
        return ModelOutput(text=self.config.model_name)

    async def achat_stream(self, messages, **kwargs):
        yield ModelOutput(text=self.config.model_name)


class FakeGraphStorage:
    def __init__(self, labels: list[str]) -> None:
        self.labels = labels
        self.search_queries: list[str] = []

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        self.search_queries.append(query)
        query_lower = query.lower().strip()
        return [
            label
            for label in self.labels
            if query_lower and query_lower in label.lower()
        ][:limit]

    async def get_all_labels(self) -> list[str]:
        return self.labels


@pytest.mark.asyncio
async def test_search_labels_matches_substrings_inside_kb_labels() -> None:
    service = KnowledgeV2Service.__new__(KnowledgeV2Service)
    service._graph = FakeGraphStorage(
        [
            "demo-kb:Alpha Beta",
            "demo-kb:Beta Root",
            "other-kb:Alpha Beta",
        ]
    )

    labels = await service.search_labels("demo-kb", query="Beta", limit=10)

    assert service._graph.search_queries == ["Beta"]
    assert labels == ["Beta Root", "Alpha Beta"]


class FakeVectorStorageForEmbeddingBinding:
    def __init__(self) -> None:
        self._embedding_func = None


class FakeRegistryForEmbeddingBinding:
    def __init__(self, embeddings) -> None:
        self.embeddings = embeddings

    def get_embeddings(self):
        return self.embeddings


class FakeEmbeddingsForEmbeddingBinding:
    async def aembed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_constructor_binds_embedding_func_to_vector_storage() -> None:
    embedding_func = object()
    vector = FakeVectorStorageForEmbeddingBinding()

    service = KnowledgeV2Service(
        llm=None,
        embedding_func=embedding_func,
        kv_storage=object(),
        vector_storage=vector,
        graph_storage=object(),
        doc_status_storage=object(),
    )

    assert service._embedding_func is embedding_func
    assert vector._embedding_func is embedding_func


def test_lazy_rebuild_embedding_binds_embedding_func_to_vector_storage() -> None:
    vector = FakeVectorStorageForEmbeddingBinding()
    service = KnowledgeV2Service.__new__(KnowledgeV2Service)
    service._embedding_func = None
    service._registry = FakeRegistryForEmbeddingBinding(FakeEmbeddingsForEmbeddingBinding())
    service._vector = vector

    service._try_rebuild_embedding()

    assert service._embedding_func is not None
    assert vector._embedding_func is service._embedding_func


def test_lazy_rebuild_llm_refreshes_when_registry_default_changes() -> None:
    registry = ModelRegistry()
    old_llm = FakeLLM(LLMConfig(model_name="old-openai", model_type="test"))
    new_llm = FakeLLM(LLMConfig(model_name="local-codex", model_type="test"))
    registry.register_llm("old-openai", old_llm, is_default=True)

    service = KnowledgeV2Service.__new__(KnowledgeV2Service)
    service._llm = None
    service._query_engine = object()
    service._registry = registry

    service._try_rebuild_llm()
    assert service._llm is old_llm

    registry.register_llm("local-codex", new_llm, is_default=True)
    service._try_rebuild_llm()

    assert service._llm is new_llm
    assert service._query_engine is None


@pytest.mark.asyncio
async def test_query_stream_filters_codex_startup_notice() -> None:
    async def stream():
        yield "我会按当前可用上下文回答，并先读取会话启动要求对应的技能说明。"
        yield "知识库主要讲了配方模板功能。"

    service = KnowledgeV2Service.__new__(KnowledgeV2Service)
    chunks = []
    async for chunk in service._wrap_stream_with_fallback(
        stream(),
        param=QueryParam(query="知识库讲了什么？"),
        references=[],
    ):
        chunks.append(chunk)

    assert chunks == ["知识库主要讲了配方模板功能。"]

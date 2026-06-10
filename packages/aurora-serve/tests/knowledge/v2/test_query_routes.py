import json

import pytest

from aurora_serve.knowledge.v2.query_routes import query_data, query_stream
from aurora_serve.knowledge.v2.schemas import QueryRequest


async def _explode_before_first_chunk():
    if False:
        yield ""
    raise RuntimeError("Connection error.")


async def _single_chunk():
    yield "回答"


class FakeKnowledgeV2FailingStreamService:
    async def query(self, **kwargs):
        return {
            "response": "",
            "references": [
                {"reference_id": "1", "file_path": "data/uploads/knowledge/配方模板.txt"}
            ],
            "stream_iterator": _explode_before_first_chunk(),
        }


class FakeKnowledgeV2StreamingService:
    async def query(self, **kwargs):
        return {
            "response": "",
            "references": [
                {"reference_id": "1", "file_path": "data/uploads/knowledge/配方模板.txt"}
            ],
            "stream_iterator": _single_chunk(),
        }


class FakeKnowledgeV2NonStreamingStreamService:
    async def query(self, **kwargs):
        return {
            "response": "完整回答",
            "references": [
                {"reference_id": "1", "file_path": "data/uploads/knowledge/配方模板.txt"}
            ],
            "stream_iterator": None,
        }


class FakeKnowledgeV2DataService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def query(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "entities": [{"entity_name": "配方管理"}],
            "relationships": [],
            "chunks": [{"content": "配方管理用于维护配方。"}],
            "references": [{"reference_id": "1", "file_path": "配方模板.txt"}],
            "hl_keywords": [],
            "ll_keywords": ["配方管理"],
        }


@pytest.mark.asyncio
async def test_stream_query_emits_references_before_first_response_chunk():
    response = await query_stream(
        name="demo-kb",
        req=QueryRequest(query="配方管理", mode="mix", stream=True),
        service=FakeKnowledgeV2StreamingService(),
    )

    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    payloads = [json.loads(line) for line in chunks if line.strip()]

    assert payloads == [
        {
            "references": [
                {
                    "reference_id": "1",
                    "file_path": "data/uploads/knowledge/配方模板.txt",
                }
            ]
        },
        {"response": "回答"},
    ]


@pytest.mark.asyncio
async def test_stream_query_keeps_references_when_stream_fails_before_first_chunk():
    response = await query_stream(
        name="demo-kb",
        req=QueryRequest(query="配方管理", mode="mix", stream=True),
        service=FakeKnowledgeV2FailingStreamService(),
    )

    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    payloads = [json.loads(line) for line in chunks if line.strip()]

    assert payloads == [
        {
            "references": [
                {
                    "reference_id": "1",
                    "file_path": "data/uploads/knowledge/配方模板.txt",
                }
            ]
        },
        {"error": "Connection error."},
    ]


@pytest.mark.asyncio
async def test_stream_query_non_streaming_fallback_includes_references():
    response = await query_stream(
        name="demo-kb",
        req=QueryRequest(query="配方管理", mode="mix", stream=False),
        service=FakeKnowledgeV2NonStreamingStreamService(),
    )

    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    payloads = [json.loads(line) for line in chunks if line.strip()]

    assert payloads == [
        {
            "response": "完整回答",
            "references": [
                {
                    "reference_id": "1",
                    "file_path": "data/uploads/knowledge/配方模板.txt",
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_query_data_forces_context_only_retrieval():
    service = FakeKnowledgeV2DataService()

    response = await query_data(
        name="demo-kb",
        req=QueryRequest(query="配方管理", mode="mix", stream=True),
        service=service,
    )

    assert response.data["chunks"] == [{"content": "配方管理用于维护配方。"}]
    assert service.calls[0]["only_need_context"] is True
    assert service.calls[0]["only_need_prompt"] is False

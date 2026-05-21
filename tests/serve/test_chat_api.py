import json
import time

import pytest
from fastapi.testclient import TestClient

from aurora_core.model.adapter.openai_adapter import OpenAILLM
from aurora_core.model.registry import ModelRegistry
from aurora_core.schema.model import LLMConfig
from aurora_serve.chat.service import ChatService
from aurora_serve.server import create_app


@pytest.fixture
def client():
    app = create_app()
    # Override with fake service to avoid real LLM calls
    registry = ModelRegistry()

    class FakeLLM:
        config = LLMConfig(model_name="fake", model_type="test")
        calls = 0

        async def achat(self, messages, **kwargs):
            from aurora_core.schema.message import ModelOutput

            self.calls += 1
            if self.calls == 1 and "column_analysis" in str(messages[0].content):
                return ModelOutput(
                    text=(
                        '{"data_analysis":"销售数据","column_analysis":['
                        '{"old_column_name":"类别","new_column_name":"category","column_description":"类别"},'
                        '{"old_column_name":"销售额","new_column_name":"sales_amount","column_description":"销售额"}'
                        '],"analysis_program":["按类别统计"]}'
                    )
                )
            if "data_analysis_table" in str(messages[0].content):
                return ModelOutput(
                    text=(
                        "统计如下：<api-call><name>response_bar_chart</name><args><sql>"
                        "SELECT category, SUM(sales_amount) AS total_sales "
                        "FROM data_analysis_table GROUP BY category ORDER BY total_sales DESC;"
                        "</sql></args></api-call>"
                    )
                )
            return ModelOutput(text="hello from fake")

        async def achat_stream(self, messages, **kwargs):
            from aurora_core.schema.message import ModelOutput

            yield ModelOutput(text="hello")
            yield ModelOutput(text=" from fake")

    registry.register_llm("fake", FakeLLM())
    app.state.chat_service = ChatService(registry)
    return TestClient(app)


def test_chat_completions_non_stream(client):
    resp = client.post(
        "/api/v1/chat/completions",
        json={"model": "fake", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "hello from fake"


def test_chat_completions_stream(client):
    resp = client.post(
        "/api/v1/chat/completions",
        json={
            "model": "fake",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    body = resp.read().decode()
    assert "data:" in body
    assert "[DONE]" in body


def test_react_agent_stream_emits_dbgpt_events_and_html_report(client, tmp_path):
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("类别,销售额\nA,10\nA,15\nB,7\n", encoding="utf-8")

    resp = client.post(
        "/api/v1/chat/react-agent",
        json={
            "model_name": "fake",
            "user_input": "按类别统计销售额",
            "ext_info": {"file_path": str(csv_path), "file_name": "sales.csv"},
        },
    )

    assert resp.status_code == 200
    body = resp.read().decode()
    assert '"type": "step.start"' in body
    assert '"type": "step.meta"' in body
    assert '"type": "step.chunk"' in body
    assert '"output_type": "html"' in body
    assert '"title": "Report"' in body
    assert '"type": "final"' in body
    assert '"type": "done"' in body


def test_session_message_upsert_replaces_existing_message_and_loads_legacy_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("AURORA_METADATA_DB", str(tmp_path / "aurora.db"))
    monkeypatch.setenv("AURORA_STORAGE_DIR", str(tmp_path / "storage"))
    app = create_app()
    registry = ModelRegistry()
    app.state.chat_service = ChatService(registry)

    with TestClient(app) as local_client:
        created = local_client.post("/api/v1/chat/sessions")
        session_id = created.json()["session_id"]

        first = local_client.put(
            f"/api/v1/chat/sessions/{session_id}/messages/assistant-1",
            json={
                "type": "assistant",
                "role": "assistant",
                "content": "draft",
                "events": [{"kind": "text", "text": "draft"}],
            },
        )
        assert first.status_code == 200

        second = local_client.put(
            f"/api/v1/chat/sessions/{session_id}/messages/assistant-1",
            json={
                "type": "assistant",
                "role": "assistant",
                "content": "final",
                "events": [{"kind": "text", "text": "final"}],
                "end_time": 1234.5,
            },
        )
        assert second.status_code == 200

        service = app.state.chat_service
        legacy_line = {
            "type": "user",
            "role": "user",
            "content": "legacy",
            "timestamp": time.time(),
        }
        with service.session_manager._session_file_path(session_id).open("a") as f:
            f.write(
                json.dumps(legacy_line, ensure_ascii=False) + "\n",
            )

        loaded_session = service.session_manager.load_session(session_id)
        assert loaded_session is not None
        service.session_manager._save_session_meta(loaded_session)

        loaded = local_client.get(f"/api/v1/chat/sessions/{session_id}")
        assert loaded.status_code == 200
        messages = loaded.json()["messages"]
        assistant_messages = [m for m in messages if m.get("id") == "assistant-1"]
        assert len(assistant_messages) == 1
        assert assistant_messages[0]["content"] == "final"
        assert assistant_messages[0]["end_time"] == 1234.5
        assert any(m["content"] == "legacy" and m.get("id") for m in messages)
        assert loaded.json()["session"]["message_count"] == 2

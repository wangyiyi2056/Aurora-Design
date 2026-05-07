import pytest
import sqlite3

from aurora_core.model.base import BaseLLM
from aurora_core.model.registry import ModelRegistry
from aurora_core.schema.message import Message, ModelOutput
from aurora_core.schema.model import LLMConfig
from aurora_serve.chat.schema import ChatRequest, ChatMessage, ModelConfig
from aurora_serve.chat.service import ChatService
from aurora_serve.datasource.schema import DBConfig
from aurora_serve.datasource.service import DatasourceService


class FakeLLM(BaseLLM):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.calls = 0

    async def achat(self, messages, **kwargs):
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
        return ModelOutput(text="fake response")

    async def achat_stream(self, messages, **kwargs):
        yield ModelOutput(text="fake")
        yield ModelOutput(text=" response")


@pytest.fixture
def service():
    registry = ModelRegistry()
    registry.register_llm("fake", FakeLLM(LLMConfig(model_name="fake", model_type="test")))
    return ChatService(registry)


@pytest.mark.asyncio
async def test_chat_service_chat(service):
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="hi")],
    )
    resp = await service.chat(req)
    assert resp.choices[0].message.content == "fake response"
    assert resp.model == "fake"


def test_chat_service_prefers_saved_runtime_when_model_config_has_no_plain_api_key(service):
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="hi")],
        model_config=ModelConfig(
            model_name="fake",
            base_url="",
            api_key="",
            model_type="llm",
        ),
    )

    assert service._get_llm(req) is service.registry.get_llm("fake")


def test_chat_service_prefers_saved_runtime_when_model_config_has_masked_api_key(service):
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="hi")],
        model_config=ModelConfig(
            model_name="fake",
            base_url="https://api.example.com/v1",
            api_key="sk-t...1234",
            model_type="llm",
        ),
    )

    assert service._get_llm(req) is service.registry.get_llm("fake")


@pytest.mark.asyncio
async def test_chat_service_stream(service):
    req = ChatRequest(
        model="fake",
        messages=[ChatMessage(role="user", content="hi")],
        stream=True,
    )
    chunks = []
    async for line in service.chat_stream(req):
        chunks.append(line)
    assert any("fake" in chunk for chunk in chunks)
    assert any("[DONE]" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_chat_service_auto_triggers_excel_analysis_for_file_url(service, tmp_path):
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("类别,销售额\nA,10\nA,15\nB,7\n", encoding="utf-8")

    req = ChatRequest(
        model="fake",
        messages=[
            ChatMessage(
                role="user",
                content=[
                    {
                        "type": "file_url",
                        "file_url": {
                            "url": str(csv_path),
                            "file_name": "sales.csv",
                        },
                    },
                    {"type": "text", "text": "按类别统计销售额"},
                ],
            )
        ],
    )

    resp = await service.chat(req)

    assert "```vis-chart" in resp.choices[0].message.content
    assert "response_bar_chart" in resp.choices[0].message.content


@pytest.mark.asyncio
async def test_chat_service_stream_emits_excel_pipeline_steps(service, tmp_path):
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("类别,销售额\nA,10\nA,15\nB,7\n", encoding="utf-8")

    req = ChatRequest(
        model="fake",
        messages=[
            ChatMessage(
                role="user",
                content=[
                    {
                        "type": "file_url",
                        "file_url": {
                            "url": str(csv_path),
                            "file_name": "sales.csv",
                        },
                    },
                    {"type": "text", "text": "按类别统计销售额"},
                ],
            )
        ],
        stream=True,
    )

    chunks = []
    async for line in service.chat_stream(req):
        chunks.append(line)
    body = "".join(chunks)

    assert '"type": "pipeline_step"' in body
    assert '"step_id": "create_duckdb"' in body
    assert '"step_id": "execute_sql"' in body
    assert "```vis-chart" in body


@pytest.mark.asyncio
async def test_chat_service_uses_ext_info_database_name_for_sql_questions(tmp_path):
    db_path = tmp_path / "sales.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("create table sales (category text, amount integer)")
        conn.executemany("insert into sales values (?, ?)", [("A", 10), ("A", 15), ("B", 7)])

    class SQLFakeLLM(FakeLLM):
        async def achat(self, messages, **kwargs):
            return ModelOutput(text="SELECT category, SUM(amount) AS total FROM sales GROUP BY category")

    registry = ModelRegistry()
    registry.register_llm("fake", SQLFakeLLM(LLMConfig(model_name="fake", model_type="test")))
    datasource = DatasourceService()
    datasource.add_connection(
        DBConfig(name="sales-db", db_type="sqlite", database=str(db_path))
    )
    service = ChatService(registry, datasource_service=datasource)

    resp = await service.chat(
        ChatRequest(
            model="fake",
            messages=[ChatMessage(role="user", content="sum sales by category")],
            ext_info={"database_name": "sales-db"},
        )
    )

    content = resp.choices[0].message.content
    assert "SQL:" in content
    assert "Result:" in content
    assert "A" in content
    assert "25" in content


@pytest.mark.asyncio
async def test_chat_service_stream_uses_ext_info_database_name(tmp_path):
    db_path = tmp_path / "sales.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("create table sales (category text, amount integer)")
        conn.executemany("insert into sales values (?, ?)", [("A", 10), ("A", 15), ("B", 7)])

    class SQLFakeLLM(FakeLLM):
        async def achat(self, messages, **kwargs):
            return ModelOutput(text="SELECT category, SUM(amount) AS total FROM sales GROUP BY category")

    registry = ModelRegistry()
    registry.register_llm("fake", SQLFakeLLM(LLMConfig(model_name="fake", model_type="test")))
    datasource = DatasourceService()
    datasource.add_connection(
        DBConfig(name="sales-db", db_type="sqlite", database=str(db_path))
    )
    service = ChatService(registry, datasource_service=datasource)

    chunks = []
    async for chunk in service.chat_stream(
        ChatRequest(
            model="fake",
            messages=[ChatMessage(role="user", content="sum sales by category")],
            stream=True,
            ext_info={"database_name": "sales-db"},
        )
    ):
        chunks.append(chunk)

    body = "".join(chunks)
    assert "SQL:" in body
    assert "Result:" in body
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_chat_service_injects_knowledge_context_from_ext_info():
    class KnowledgeAwareLLM(FakeLLM):
        async def achat(self, messages, **kwargs):
            combined = "\n".join(str(message.content) for message in messages)
            if "Knowledge context" in combined and "Aurora stores metadata" in combined:
                return ModelOutput(text="used knowledge context")
            return ModelOutput(text="missing knowledge context")

    class FakeKnowledgeService:
        async def query(self, name: str, query: str, top_k: int = 5):
            assert name == "docs"
            assert query == "How does Aurora store metadata?"
            return {
                "results": [
                    {
                        "content": "Aurora stores metadata in SQLite.",
                        "metadata": {"source": "doc.txt"},
                    }
                ]
            }

    registry = ModelRegistry()
    registry.register_llm("fake", KnowledgeAwareLLM(LLMConfig(model_name="fake", model_type="test")))
    service = ChatService(registry, knowledge_service=FakeKnowledgeService())

    resp = await service.chat(
        ChatRequest(
            model="fake",
            messages=[ChatMessage(role="user", content="How does Aurora store metadata?")],
            ext_info={"knowledge_ids": ["docs"]},
        )
    )

    assert resp.choices[0].message.content == "used knowledge context"


@pytest.mark.asyncio
async def test_chat_service_stream_injects_knowledge_context_from_ext_info():
    class KnowledgeAwareLLM(FakeLLM):
        async def achat(self, messages, **kwargs):
            combined = "\n".join(str(message.content) for message in messages)
            if "Knowledge context" in combined and "Aurora stores metadata" in combined:
                return ModelOutput(text="used knowledge")
            return ModelOutput(text="missing knowledge")

        async def achat_stream(self, messages, **kwargs):
            combined = "\n".join(str(message.content) for message in messages)
            if "Knowledge context" in combined and "Aurora stores metadata" in combined:
                yield ModelOutput(text="used knowledge")
            else:
                yield ModelOutput(text="missing knowledge")

    class FakeKnowledgeService:
        async def query(self, name: str, query: str, top_k: int = 5):
            return {
                "results": [
                    {
                        "content": "Aurora stores metadata in SQLite.",
                        "metadata": {"source": "doc.txt"},
                    }
                ]
            }

    registry = ModelRegistry()
    registry.register_llm("fake", KnowledgeAwareLLM(LLMConfig(model_name="fake", model_type="test")))
    service = ChatService(registry, knowledge_service=FakeKnowledgeService())

    chunks = []
    async for chunk in service.chat_stream(
        ChatRequest(
            model="fake",
            messages=[ChatMessage(role="user", content="How does Aurora store metadata?")],
            stream=True,
            ext_info={"knowledge_base": "docs"},
        )
    ):
        chunks.append(chunk)

    body = "".join(chunks)
    assert "used knowl" in body
    assert "edge" in body
    assert "[DONE]" in body


@pytest.mark.asyncio
async def test_chat_service_limits_tools_when_skill_selected(service):
    seen_tools = []

    async def capture_tools(messages, **kwargs):
        seen_tools.extend(tool["function"]["name"] for tool in kwargs.get("tools") or [])
        return ModelOutput(text="ok")

    llm = service.registry.get_llm("fake")
    llm.achat = capture_tools

    service.tool_registry.register(
        type(
            "DummyTool",
            (),
            {
                "name": "selected_skill",
                "description": "Selected skill",
                "input_schema": {"type": "object", "properties": {}},
                "is_active": True,
            },
        )()
    )
    service.tool_registry.register(
        type(
            "OtherTool",
            (),
            {
                "name": "other_skill",
                "description": "Other skill",
                "input_schema": {"type": "object", "properties": {}},
                "is_active": True,
            },
        )()
    )

    await service.chat(
        ChatRequest(
            model="fake",
            messages=[ChatMessage(role="user", content="run it")],
            select_param="selected_skill",
        )
    )

    assert "selected_skill" in seen_tools
    assert "other_skill" not in seen_tools

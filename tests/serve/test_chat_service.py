import pytest

from chatbi_core.model.base import BaseLLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message, ModelOutput
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.chat.schema import ChatRequest, ChatMessage
from chatbi_serve.chat.service import ChatService


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

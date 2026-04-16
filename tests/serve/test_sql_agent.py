import pytest

from chatbi_core.model.base import BaseLLM
from chatbi_core.model.registry import ModelRegistry
from chatbi_core.schema.message import Message, ModelOutput
from chatbi_core.schema.model import LLMConfig
from chatbi_serve.agent.sql_agent import SQLAgent
from chatbi_serve.datasource.schema import DBConfig
from chatbi_serve.datasource.service import DatasourceService


class FakeLLM(BaseLLM):
    async def achat(self, messages, **kwargs):
        return ModelOutput(text="SELECT * FROM users")

    async def achat_stream(self, messages, **kwargs):
        yield ModelOutput(text="SELECT * FROM users")


@pytest.fixture
def sql_agent():
    registry = ModelRegistry()
    registry.register_llm("fake", FakeLLM(LLMConfig(model_name="fake", model_type="test")))
    ds = DatasourceService()
    ds.add_connection(DBConfig(name="test", db_type="sqlite", database=":memory:"))
    agent = SQLAgent(registry, ds, datasource_name="test")
    return agent


@pytest.mark.asyncio
async def test_sql_agent_is_sql_question(sql_agent):
    assert sql_agent.is_sql_question("查询销售额 top10") is True
    assert sql_agent.is_sql_question("你好") is False


@pytest.mark.asyncio
async def test_sql_agent_run(sql_agent):
    # Create table first
    conn = sql_agent.datasource.get_connector("test")
    conn.run("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.run("INSERT INTO users (name) VALUES ('Alice')")

    success, result = await sql_agent.run("Show me all users")
    assert success is True
    assert "SELECT * FROM users" in result
    assert "Alice" in result

import json
from pathlib import Path

import pytest

from aurora_core.model.base import BaseLLM
from aurora_core.schema.message import Message, ModelOutput
from aurora_core.schema.model import LLMConfig
from aurora_serve.excel.api_call import ApiCall
from aurora_serve.excel.pipeline import ExcelAnalysisPipeline
from aurora_serve.excel.reader import ExcelReader


class FakeExcelLLM(BaseLLM):
    def __init__(self) -> None:
        super().__init__(LLMConfig(model_name="fake-excel", model_type="test"))
        self.calls = 0

    async def achat(self, messages: list[Message], **kwargs):
        self.calls += 1
        if self.calls == 1:
            return ModelOutput(
                text=json.dumps(
                    {
                        "data_analysis": "销售明细数据",
                        "column_analysis": [
                            {
                                "old_column_name": "类别",
                                "new_column_name": "类别",
                                "column_description": "商品类别",
                            },
                            {
                                "old_column_name": "销售额",
                                "new_column_name": "123 销售额!",
                                "column_description": "销售金额",
                            },
                            {
                                "old_column_name": "销售额",
                                "new_column_name": "123 销售额!",
                                "column_description": "重复字段应被去重",
                            },
                        ],
                        "analysis_program": ["按类别统计销售额"],
                    },
                    ensure_ascii=False,
                )
            )
        return ModelOutput(
            text=(
                "按类别统计如下："
                "<api-call><name>response_bar_chart</name><args><sql>"
                "SELECT category, SUM(col_123_sales_amount) AS total_sales "
                "FROM data_analysis_table GROUP BY category ORDER BY total_sales DESC;"
                "</sql></args></api-call>"
            )
        )

    async def achat_stream(self, messages, **kwargs):
        yield ModelOutput(text="")


def _write_sales_csv(path: Path) -> None:
    path.write_text("类别,销售额\nA,10\nA,15\nB,7\n", encoding="utf-8")


def test_excel_reader_import_is_idempotent_and_blocks_writes(tmp_path):
    csv_path = tmp_path / "sales.csv"
    _write_sales_csv(csv_path)

    reader = ExcelReader(str(csv_path))
    reader.import_file()
    cols, rows = reader.get_sample_data(reader.temp_table)

    assert cols == ["类别", "销售额"]
    assert rows
    with pytest.raises(ValueError, match="Only read-only"):
        reader.run_sql("DROP TABLE temp_table")


@pytest.mark.asyncio
async def test_excel_pipeline_sanitizes_columns_and_renders_vis_chart(tmp_path):
    csv_path = tmp_path / "sales.csv"
    _write_sales_csv(csv_path)
    events: list[tuple[str, str]] = []

    pipeline = ExcelAnalysisPipeline(
        llm=FakeExcelLLM(),
        file_path=str(csv_path),
        emit_step=lambda step_id, status, detail=None: events.append((step_id, status)),
    )

    prepare = await pipeline.prepare()
    schema = pipeline.reader.get_create_table_sql("data_analysis_table")
    rendered = await pipeline.analyze("按类别统计销售额")

    assert prepare.column_analysis[0]["new_column_name"] == "category"
    assert "col_123_sales_amount" in schema
    assert "col_123_sales_amount_2" in schema
    assert "```vis-chart" in rendered
    payload = rendered.split("```vis-chart", 1)[1].split("```", 1)[0].strip()
    chart = json.loads(payload)
    assert chart["type"] == "response_bar_chart"
    assert chart["data"][0]["total_sales"] == 25
    assert ("execute_sql", "completed") in events


def test_api_call_rejects_mutating_sql(tmp_path):
    csv_path = tmp_path / "sales.csv"
    _write_sales_csv(csv_path)
    reader = ExcelReader(str(csv_path))

    rendered = ApiCall.render(
        "<api-call><name>response_table</name><args><sql>"
        "DELETE FROM temp_table"
        "</sql></args></api-call>",
        reader,
    )

    assert "Chart Error" in rendered
    assert "Only read-only" in rendered

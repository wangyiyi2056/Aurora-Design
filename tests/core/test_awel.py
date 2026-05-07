import pytest

from aurora_core.awel import DAGBuilder, DAGExecutor, MapOperator


class AddOneOperator(MapOperator):
    async def map(self, input_value):
        if isinstance(input_value, list):
            input_value = input_value[0]
        return input_value + 1


class MultiplyOperator(MapOperator):
    async def map(self, input_value):
        if isinstance(input_value, list):
            input_value = input_value[0]
        return input_value * 2


@pytest.mark.asyncio
async def test_dag_builder_and_executor():
    op1 = AddOneOperator(name="add")
    op2 = MultiplyOperator(name="mul")
    op1 >> op2
    builder = DAGBuilder()
    builder.add_node(op1).add_node(op2)
    dag = builder.build()
    executor = DAGExecutor(dag)
    outputs = await executor.execute(3)
    assert outputs["add"] == 4
    assert outputs["mul"] == 8


@pytest.mark.asyncio
async def test_dag_with_multiple_upstream():
    op1 = AddOneOperator(name="a")
    op2 = AddOneOperator(name="b")
    op3 = MultiplyOperator(name="c")
    op1 >> op3
    op2 >> op3
    builder = DAGBuilder()
    builder.add_node(op1).add_node(op2).add_node(op3)
    dag = builder.build()
    executor = DAGExecutor(dag)
    # Note: current DAGExecutor passes list of upstream outputs as ctx
    outputs = await executor.execute(1)
    assert outputs["a"] == 2
    assert outputs["b"] == 2
    assert outputs["c"] == 4  # 2 * 2 from list [2, 2] -> str(2) * 2 -> '22'... wait
    # Actually MultiplyOperator treats list by taking first element.
    # With two upstreams, ctx is [2, 2], takes 2, returns 4
    assert outputs["c"] == 4

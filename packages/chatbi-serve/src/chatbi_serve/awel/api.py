from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from chatbi_core.awel import DAGBuilder, DAGExecutor
from chatbi_core.awel.operator.base import MapOperator

router = APIRouter(prefix="/awel", tags=["awel"])


class FlowRunRequest(BaseModel):
    initial_input: Any = None


class FlowDefinition(BaseModel):
    name: str
    operators: List[Dict[str, Any]]
    edges: List[Dict[str, str]]


class EchoOperator(MapOperator):
    async def map(self, input_value: Any) -> Any:
        return f"echo: {input_value}"


class UpperOperator(MapOperator):
    async def map(self, input_value: Any) -> Any:
        if isinstance(input_value, list):
            input_value = input_value[0]
        return str(input_value).upper()


@router.post("/run")
async def run_flow(req: FlowRunRequest) -> Dict[str, Any]:
    op1 = EchoOperator(name="echo")
    op2 = UpperOperator(name="upper")
    op1 >> op2
    builder = DAGBuilder()
    builder.add_node(op1).add_node(op2)
    dag = builder.build()
    executor = DAGExecutor(dag)
    outputs = await executor.execute(req.initial_input or "hello")
    return {"outputs": outputs}


@router.get("/operators")
async def list_operators() -> List[Dict[str, str]]:
    return [
        {"name": "EchoOperator", "type": "MapOperator"},
        {"name": "UpperOperator", "type": "MapOperator"},
    ]

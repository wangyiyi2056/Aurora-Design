from fastapi import FastAPI
from pydantic import BaseModel

from sandbox.executor.docker import DockerCodeExecutor

app = FastAPI(title="ChatBI Sandbox")
executor = DockerCodeExecutor()


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"


@app.post("/execute")
async def execute_code(req: ExecuteRequest):
    result = await executor.execute(req.code, req.language)
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}

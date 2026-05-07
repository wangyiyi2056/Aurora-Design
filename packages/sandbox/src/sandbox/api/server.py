from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from sandbox.executor.docker import DockerCodeExecutor

app = FastAPI(title="Aurora Sandbox")
executor = DockerCodeExecutor()


class ExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    output_files: List[str] | None = None


@app.post("/execute")
async def execute_code(req: ExecuteRequest):
    result = await executor.execute(
        req.code, req.language, output_files=req.output_files
    )
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "files": result.files,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int


class DockerCodeExecutor:
    def __init__(
        self,
        image: str = "python:3.11-slim",
        timeout: int = 30,
        memory: str = "128m",
        network: str = "none",
    ):
        self.image = image
        self.timeout = timeout
        self.memory = memory
        self.network = network

    async def execute(self, code: str, language: str = "python") -> ExecutionResult:
        if language != "python":
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Language '{language}' not supported yet.",
                exit_code=-1,
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text(code, encoding="utf-8")
            container_name = f"chatbi-sandbox-{uuid.uuid4().hex[:8]}"
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                self.network,
                "--memory",
                self.memory,
                "--name",
                container_name,
                "-v",
                f"{tmpdir}:/workspace:ro",
                self.image,
                "python",
                "/workspace/script.py",
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                )
            except subprocess.TimeoutExpired:
                # Force kill container if timed out
                subprocess.run(["docker", "kill", container_name], capture_output=True)
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Execution timed out.",
                    exit_code=-1,
                )
            except FileNotFoundError:
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Docker not found. Is Docker installed and running?",
                    exit_code=-1,
                )
            except Exception as e:
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=str(e),
                    exit_code=-1,
                )

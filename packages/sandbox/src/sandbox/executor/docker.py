import base64
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    files: Dict[str, str] = field(default_factory=dict)


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

    async def execute(
        self,
        code: str,
        language: str = "python",
        output_files: List[str] | None = None,
    ) -> ExecutionResult:
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
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(exist_ok=True)

            container_name = f"aurora-sandbox-{uuid.uuid4().hex[:8]}"
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
                "-v",
                f"{output_dir}:/workspace/output",
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

                files: Dict[str, str] = {}
                if output_files and proc.returncode == 0:
                    for fname in output_files:
                        fpath = output_dir / fname
                        if fpath.exists():
                            files[fname] = base64.b64encode(fpath.read_bytes()).decode(
                                "utf-8"
                            )

                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    files=files,
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

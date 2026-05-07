from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterable


AgentEvent = dict[str, Any]


DEFAULT_MODEL_OPTION = {"id": "default", "label": "Default (CLI config)"}


@dataclass(frozen=True)
class AgentDef:
    id: str
    name: str
    bin: str
    version_args: tuple[str, ...] = ("--version",)
    fallback_bins: tuple[str, ...] = ()
    fallback_models: tuple[dict[str, str], ...] = field(default_factory=tuple)
    reasoning_options: tuple[dict[str, str], ...] = field(default_factory=tuple)
    prompt_via_stdin: bool = True
    stream_format: str = "plain"
    event_parser: str | None = None
    env: dict[str, str] = field(default_factory=dict)


AGENT_DEFS: tuple[AgentDef, ...] = (
    AgentDef(
        id="claude",
        name="Claude Code",
        bin="claude",
        fallback_bins=("openclaude",),
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "sonnet", "label": "Sonnet (alias)"},
            {"id": "opus", "label": "Opus (alias)"},
            {"id": "haiku", "label": "Haiku (alias)"},
            {"id": "claude-opus-4-5", "label": "claude-opus-4-5"},
            {"id": "claude-sonnet-4-5", "label": "claude-sonnet-4-5"},
            {"id": "claude-haiku-4-5", "label": "claude-haiku-4-5"},
        ),
        stream_format="claude-stream-json",
    ),
    AgentDef(
        id="codex",
        name="Codex CLI",
        bin="codex",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "gpt-5-codex", "label": "gpt-5-codex"},
            {"id": "gpt-5", "label": "gpt-5"},
            {"id": "o3", "label": "o3"},
            {"id": "o4-mini", "label": "o4-mini"},
        ),
        reasoning_options=(
            {"id": "default", "label": "Default"},
            {"id": "minimal", "label": "Minimal"},
            {"id": "low", "label": "Low"},
            {"id": "medium", "label": "Medium"},
            {"id": "high", "label": "High"},
        ),
        stream_format="json-event-stream",
        event_parser="codex",
    ),
    AgentDef(
        id="devin",
        name="Devin for Terminal",
        bin="devin",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "adaptive", "label": "adaptive"},
            {"id": "swe", "label": "swe"},
            {"id": "opus", "label": "opus"},
            {"id": "sonnet", "label": "sonnet"},
            {"id": "codex", "label": "codex"},
            {"id": "gpt", "label": "gpt"},
            {"id": "gemini", "label": "gemini"},
        ),
        stream_format="acp-json-rpc",
    ),
    AgentDef(
        id="gemini",
        name="Gemini CLI",
        bin="gemini",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "gemini-2.5-pro", "label": "gemini-2.5-pro"},
            {"id": "gemini-2.5-flash", "label": "gemini-2.5-flash"},
        ),
        stream_format="json-event-stream",
        event_parser="gemini",
        env={"GEMINI_CLI_TRUST_WORKSPACE": "true"},
    ),
    AgentDef(
        id="opencode",
        name="OpenCode",
        bin="opencode",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "anthropic/claude-sonnet-4-5", "label": "anthropic/claude-sonnet-4-5"},
            {"id": "openai/gpt-5", "label": "openai/gpt-5"},
            {"id": "google/gemini-2.5-pro", "label": "google/gemini-2.5-pro"},
        ),
        stream_format="json-event-stream",
        event_parser="opencode",
    ),
    AgentDef(
        id="hermes",
        name="Hermes",
        bin="hermes",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "openai-codex:gpt-5.5", "label": "gpt-5.5 (openai-codex:gpt-5.5)"},
            {"id": "openai-codex:gpt-5.4", "label": "gpt-5.4 (openai-codex:gpt-5.4)"},
            {"id": "openai-codex:gpt-5.4-mini", "label": "gpt-5.4-mini (openai-codex:gpt-5.4-mini)"},
        ),
        stream_format="acp-json-rpc",
    ),
    AgentDef(
        id="kimi",
        name="Kimi CLI",
        bin="kimi",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "kimi-k2-turbo-preview", "label": "kimi-k2-turbo-preview"},
            {"id": "moonshot-v1-8k", "label": "moonshot-v1-8k"},
            {"id": "moonshot-v1-32k", "label": "moonshot-v1-32k"},
        ),
        stream_format="acp-json-rpc",
    ),
    AgentDef(
        id="cursor-agent",
        name="Cursor Agent",
        bin="cursor-agent",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "auto", "label": "auto"},
            {"id": "sonnet-4", "label": "sonnet-4"},
            {"id": "sonnet-4-thinking", "label": "sonnet-4-thinking"},
            {"id": "gpt-5", "label": "gpt-5"},
        ),
        stream_format="json-event-stream",
        event_parser="cursor-agent",
    ),
    AgentDef(
        id="qwen",
        name="Qwen Code",
        bin="qwen",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "qwen3-coder-plus", "label": "qwen3-coder-plus"},
            {"id": "qwen3-coder-flash", "label": "qwen3-coder-flash"},
        ),
    ),
    AgentDef(
        id="copilot",
        name="GitHub Copilot CLI",
        bin="copilot",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "claude-sonnet-4.6", "label": "Claude Sonnet 4.6"},
            {"id": "gpt-5.2", "label": "GPT-5.2"},
        ),
        prompt_via_stdin=False,
        stream_format="copilot-stream-json",
    ),
    AgentDef(
        id="pi",
        name="Pi",
        bin="pi",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "anthropic/claude-sonnet-4-5", "label": "Claude Sonnet 4.5 (anthropic)"},
            {"id": "anthropic/claude-opus-4-5", "label": "Claude Opus 4.5 (anthropic)"},
            {"id": "openai/gpt-5", "label": "GPT-5 (openai)"},
            {"id": "openai/o4-mini", "label": "o4-mini (openai)"},
            {"id": "google/gemini-2.5-pro", "label": "Gemini 2.5 Pro (google)"},
            {"id": "google/gemini-2.5-flash", "label": "Gemini 2.5 Flash (google)"},
        ),
        reasoning_options=(
            {"id": "default", "label": "Default"},
            {"id": "off", "label": "Off"},
            {"id": "minimal", "label": "Minimal"},
            {"id": "low", "label": "Low"},
            {"id": "medium", "label": "Medium"},
            {"id": "high", "label": "High"},
            {"id": "xhigh", "label": "XHigh"},
        ),
        stream_format="pi-rpc",
    ),
    AgentDef(id="kiro", name="Kiro CLI", bin="kiro-cli", fallback_models=(DEFAULT_MODEL_OPTION,), stream_format="acp-json-rpc"),
    AgentDef(id="kilo", name="Kilo", bin="kilo", fallback_models=(DEFAULT_MODEL_OPTION,), stream_format="acp-json-rpc"),
    AgentDef(id="vibe", name="Mistral Vibe CLI", bin="vibe-acp", fallback_models=(DEFAULT_MODEL_OPTION,), stream_format="acp-json-rpc"),
    AgentDef(
        id="deepseek",
        name="DeepSeek TUI",
        bin="deepseek",
        fallback_models=(
            DEFAULT_MODEL_OPTION,
            {"id": "deepseek-v4-pro", "label": "deepseek-v4-pro"},
            {"id": "deepseek-v4-flash", "label": "deepseek-v4-flash"},
        ),
    ),
)


def get_agent_def(agent_id: str) -> AgentDef:
    for agent in AGENT_DEFS:
        if agent.id == agent_id:
            return agent
    raise KeyError(f"Unknown agent: {agent_id}")


def _user_toolchain_dirs() -> list[str]:
    home = Path.home()
    candidates = [
        home / ".local" / "bin",
        home / ".cargo" / "bin",
        home / ".npm-global" / "bin",
        home / ".bun" / "bin",
        home / ".deno" / "bin",
        home / ".volta" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    return [str(path) for path in candidates if path.exists()]


def resolve_on_path(binary: str, path_env: str | None = None) -> str | None:
    search_path = os.pathsep.join(
        [path_env or os.environ.get("PATH", ""), *_user_toolchain_dirs()]
    )
    return shutil.which(binary, path=search_path)


def resolve_agent_bin(agent_id: str) -> str:
    agent = get_agent_def(agent_id)
    for binary in (agent.bin, *agent.fallback_bins):
        resolved = resolve_on_path(binary)
        if resolved:
            return resolved
    raise FileNotFoundError(f"{agent.name} CLI not found on PATH")


async def _probe_agent(agent: AgentDef) -> dict[str, Any]:
    path: str | None = None
    for binary in (agent.bin, *agent.fallback_bins):
        path = resolve_on_path(binary)
        if path:
            break
    if not path:
        return _agent_info(agent, available=False)

    version: str | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            path,
            *agent.version_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        raw = (stdout or stderr).decode("utf-8", errors="replace").strip()
        version = raw.splitlines()[0] if raw else None
    except Exception:
        version = None

    return _agent_info(agent, available=True, path=path, version=version)


def _agent_info(
    agent: AgentDef,
    *,
    available: bool,
    path: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "bin": agent.bin,
        "available": available,
        "path": path,
        "version": version,
        "models": list(agent.fallback_models),
        "reasoningOptions": list(agent.reasoning_options),
        "streamFormat": agent.stream_format,
        "promptViaStdin": agent.prompt_via_stdin,
    }


async def detect_agents() -> list[dict[str, Any]]:
    return await asyncio.gather(*(_probe_agent(agent) for agent in AGENT_DEFS))


def sanitize_custom_model(model: str | None) -> str | None:
    if model is None:
        return None
    value = model.strip()
    if not value or value == "default":
        return None
    if value.startswith("-") or len(value) > 200:
        raise ValueError("Invalid model name")
    if re.search(r"[\s\x00-\x1f\x7f]", value):
        raise ValueError("Invalid model name")
    return value


def clamp_codex_reasoning(model_id: str | None, effort: str | None) -> str | None:
    if not effort or effort == "default":
        return None
    raw = (model_id or "").strip()
    model = raw.split("/")[-1] if "/" in raw else raw
    late_family = (
        not model
        or model == "default"
        or model.startswith(("gpt-5.2", "gpt-5.3", "gpt-5.4", "gpt-5.5"))
    )
    if late_family and effort == "minimal":
        return "low"
    if model == "gpt-5.1" and effort == "xhigh":
        return "high"
    if model == "gpt-5.1-codex-mini":
        return "high" if effort in {"high", "xhigh"} else "medium"
    return effort


def build_agent_args(
    agent_id: str,
    *,
    prompt: str = "",
    model: str | None = None,
    reasoning: str | None = None,
    cwd: str | None = None,
) -> list[str]:
    selected_model = sanitize_custom_model(model)
    if agent_id == "claude":
        args = ["-p", "--output-format", "stream-json", "--verbose"]
        if selected_model:
            args.extend(["--model", selected_model])
        args.extend(["--permission-mode", "bypassPermissions"])
        return args
    if agent_id == "codex":
        args = [
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "-c",
            "sandbox_workspace_write.network_access=true",
        ]
        if cwd:
            args.extend(["-C", cwd])
        if selected_model:
            args.extend(["--model", selected_model])
        selected_reasoning = clamp_codex_reasoning(selected_model, reasoning)
        if selected_reasoning:
            args.extend(["-c", f'model_reasoning_effort="{selected_reasoning}"'])
        return args
    if agent_id == "gemini":
        args = ["--output-format", "stream-json", "--yolo"]
        if selected_model:
            args.extend(["--model", selected_model])
        return args
    if agent_id == "opencode":
        args = ["run", "--format", "json", "--dangerously-skip-permissions"]
        if selected_model:
            args.extend(["--model", selected_model])
        args.append("-")
        return args
    if agent_id == "cursor-agent":
        args = ["--print", "--output-format", "stream-json", "--stream-partial-output", "--force", "--trust"]
        if cwd:
            args.extend(["--workspace", cwd])
        if selected_model:
            args.extend(["--model", selected_model])
        return args
    if agent_id == "qwen":
        args = ["--yolo"]
        if selected_model:
            args.extend(["--model", selected_model])
        args.append("-")
        return args
    if agent_id == "copilot":
        args = ["-p", prompt, "--allow-all-tools", "--output-format", "json"]
        if selected_model:
            args.extend(["--model", selected_model])
        return args
    if agent_id == "pi":
        args = ["--mode", "rpc"]
        if selected_model:
            args.extend(["--model", selected_model])
        if reasoning and reasoning != "default":
            args.extend(["--thinking", reasoning])
        return args
    if agent_id == "deepseek":
        args = ["exec", "--auto"]
        if selected_model:
            args.extend(["--model", selected_model])
        args.append(prompt)
        return args
    if agent_id in {"devin"}:
        return ["--permission-mode", "dangerous", "--respect-workspace-trust", "false", "acp"]
    if agent_id == "hermes":
        return ["acp", "--accept-hooks"]
    if agent_id in {"kimi", "kiro", "kilo"}:
        return ["acp"]
    if agent_id == "vibe":
        return []
    raise KeyError(f"Unknown agent: {agent_id}")


def spawn_env_for_agent(agent_id: str, env: dict[str, str] | None = None) -> dict[str, str]:
    child_env = dict(env or os.environ)
    if agent_id == "claude" and not child_env.get("ANTHROPIC_BASE_URL"):
        child_env.pop("ANTHROPIC_API_KEY", None)
    try:
        child_env.update(get_agent_def(agent_id).env)
    except KeyError:
        pass
    return child_env


class ClaudeStreamParser:
    def __init__(self, on_event: Callable[[AgentEvent], None]):
        self.on_event = on_event
        self._buffer = ""
        self._text_streamed: set[str] = set()

    def feed(self, chunk: str) -> None:
        self._buffer += chunk
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._handle_line(line.strip())

    def flush(self) -> None:
        line = self._buffer.strip()
        self._buffer = ""
        if line:
            self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self.on_event({"type": "raw", "line": line})
            return
        if obj.get("type") == "system" and obj.get("subtype") == "init":
            self.on_event({"type": "status", "label": "initializing", "model": obj.get("model")})
            return
        if obj.get("type") == "stream_event":
            self._handle_stream_event(obj.get("event") or {})
            return
        if obj.get("type") == "assistant":
            message = obj.get("message") or {}
            message_id = message.get("id")
            if message_id and message_id in self._text_streamed:
                return
            for block in message.get("content") or []:
                if block.get("type") == "text" and block.get("text"):
                    self.on_event({"type": "text_delta", "delta": block["text"]})
                if block.get("type") == "tool_use":
                    self.on_event({
                        "type": "tool_use",
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": block.get("input"),
                    })
            return
        if obj.get("type") == "result":
            self.on_event({
                "type": "usage",
                "usage": obj.get("usage"),
                "costUsd": obj.get("total_cost_usd"),
                "durationMs": obj.get("duration_ms"),
            })

    def _handle_stream_event(self, event: dict[str, Any]) -> None:
        if event.get("type") == "message_start":
            message_id = (event.get("message") or {}).get("id")
            if message_id:
                self._current_message_id = message_id
            return
        delta = event.get("delta") or {}
        if event.get("type") == "content_block_delta":
            if delta.get("type") == "text_delta" and delta.get("text"):
                message_id = getattr(self, "_current_message_id", None)
                if message_id:
                    self._text_streamed.add(message_id)
                self.on_event({"type": "text_delta", "delta": delta["text"]})
            if delta.get("type") == "thinking_delta" and delta.get("thinking"):
                self.on_event({"type": "thinking_delta", "delta": delta["thinking"]})


class JsonEventStreamParser:
    def __init__(self, kind: str, on_event: Callable[[AgentEvent], None]):
        self.kind = kind
        self.on_event = on_event
        self._buffer = ""
        self._codex_tool_uses: set[str] = set()

    def feed(self, chunk: str) -> None:
        self._buffer += chunk
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._handle_line(line.strip())

    def flush(self) -> None:
        line = self._buffer.strip()
        self._buffer = ""
        if line:
            self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self.on_event({"type": "raw", "line": line})
            return
        if self.kind == "codex" and self._handle_codex(obj):
            return
        self.on_event({"type": "raw", "line": line})

    def _handle_codex(self, obj: dict[str, Any]) -> bool:
        event_type = obj.get("type")
        if event_type == "thread.started":
            self.on_event({"type": "status", "label": "initializing"})
            return True
        if event_type == "turn.started":
            self.on_event({"type": "status", "label": "running"})
            return True
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        if event_type in {"item.started", "item.completed"} and item.get("type") == "command_execution":
            item_id = item.get("id")
            if item_id and item_id not in self._codex_tool_uses:
                self._codex_tool_uses.add(item_id)
                self.on_event({
                    "type": "tool_use",
                    "id": item_id,
                    "name": "Bash",
                    "input": {"command": item.get("command", "")},
                })
            if event_type == "item.completed" and item_id:
                self.on_event({
                    "type": "tool_result",
                    "toolUseId": item_id,
                    "content": _stringify(item.get("aggregated_output", "")),
                    "isError": bool(item.get("exit_code")),
                })
            return True
        if event_type == "item.completed" and item.get("type") == "agent_message":
            text = item.get("text")
            if text:
                self.on_event({"type": "text_delta", "delta": text})
            return True
        if event_type == "turn.completed":
            self.on_event({"type": "usage", "usage": obj.get("usage")})
            return True
        return False


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


async def run_agent_stream(
    agent_id: str,
    prompt: str,
    *,
    cwd: str | None = None,
    model: str | None = None,
    reasoning: str | None = None,
) -> AsyncIterator[AgentEvent]:
    agent = get_agent_def(agent_id)
    binary = resolve_agent_bin(agent_id)
    workdir = cwd or os.getcwd()
    args = build_agent_args(agent_id, prompt=prompt, model=model, reasoning=reasoning, cwd=workdir)
    proc = await asyncio.create_subprocess_exec(
        binary,
        *args,
        cwd=workdir,
        env=spawn_env_for_agent(agent_id),
        stdin=asyncio.subprocess.PIPE if agent.prompt_via_stdin else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if agent.prompt_via_stdin and proc.stdin:
        proc.stdin.write(prompt.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()

    queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
    parser: Any
    if agent.stream_format == "claude-stream-json":
        parser = ClaudeStreamParser(queue.put_nowait)
    elif agent.stream_format == "json-event-stream":
        parser = JsonEventStreamParser(agent.event_parser or agent.id, queue.put_nowait)
    else:
        parser = None

    async def read_stdout() -> None:
        assert proc.stdout is not None
        while chunk := await proc.stdout.read(4096):
            text = chunk.decode("utf-8", errors="replace")
            if parser:
                parser.feed(text)
            else:
                queue.put_nowait({"type": "text_delta", "delta": text})
        if parser:
            parser.flush()

    async def read_stderr() -> None:
        assert proc.stderr is not None
        while chunk := await proc.stderr.read(4096):
            queue.put_nowait({
                "type": "stderr",
                "chunk": chunk.decode("utf-8", errors="replace"),
            })

    stdout_task = asyncio.create_task(read_stdout())
    stderr_task = asyncio.create_task(read_stderr())
    wait_task = asyncio.create_task(proc.wait())

    while True:
        if wait_task.done() and queue.empty() and stdout_task.done() and stderr_task.done():
            break
        try:
            yield await asyncio.wait_for(queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

    code = await wait_task
    if code != 0:
        yield {"type": "error", "message": f"{agent.name} exited with code {code}"}


def collapse_messages_for_cli(messages: Iterable[Any]) -> str:
    sections: list[str] = []
    for message in messages:
        role = getattr(message, "role", None) or message.get("role", "user")
        content = getattr(message, "content", None) if not isinstance(message, dict) else message.get("content")
        sections.append(f"## {role}\n{_message_content_to_text(content)}")
    return "\n\n".join(sections)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            elif hasattr(part, "text"):
                parts.append(str(part.text or ""))
            else:
                parts.append(str(part))
        return "\n".join(item for item in parts if item)
    return str(content or "")

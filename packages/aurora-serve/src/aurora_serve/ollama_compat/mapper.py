"""Mapping logic between Ollama requests and Aurora RAG queries.

Responsibilities:
- Parse mode prefixes from message content (``/local``, ``/global``, etc.)
- Detect OpenWebUI passthrough patterns
- Convert Ollama messages to conversation history dicts
- Estimate token counts
"""

from __future__ import annotations

from typing import List

from aurora_serve.ollama_compat.models import OllamaMessage

# ── Mode Prefix Table ───────────────────────────────────────────────

_MODE_PREFIXES: dict[str, str] = {
    "/local": "local",
    "/global": "global",
    "/hybrid": "hybrid",
    "/naive": "naive",
    "/mix": "mix",
    "/bypass": "bypass",
    "/context": "mix",
    "/localcontext": "local",
    "/globalcontext": "global",
    "/hybridcontext": "hybrid",
    "/naivecontext": "naive",
    "/mixcontext": "mix",
}

# OpenWebUI injects ``\n<chat_history>\nUSER:`` when forwarding
# conversations that should bypass RAG entirely.
_OPENWEBUI_PASSTHROUGH_MARKER = "\n<chat_history>\nUSER:"


# ── Public API ──────────────────────────────────────────────────────


def parse_mode_and_query(content: str) -> tuple[str, str]:
    """Extract RAG mode prefix and clean query from message content.

    Returns a ``(mode, clean_query)`` tuple.  When no prefix is found the
    default mode is ``"mix"``.
    """
    stripped = content.strip()
    # Sort by longest prefix first so "/localcontext" matches before "/local"
    for prefix, mode in sorted(_MODE_PREFIXES.items(), key=lambda kv: -len(kv[0])):
        if stripped.startswith(prefix):
            clean = stripped[len(prefix):].strip()
            return mode, clean
    return "mix", stripped


def is_openwebui_passthrough(content: str) -> bool:
    """Detect the OpenWebUI ``chat_history`` pattern that should bypass RAG."""
    return _OPENWEBUI_PASSTHROUGH_MARKER in content


def build_conversation_history(
    messages: List[OllamaMessage],
) -> list[dict[str, str]]:
    """Convert OllamaMessage list to conversation_history dicts.

    Excludes the last user message (it becomes the current query).
    """
    history: list[dict[str, str]] = []
    for msg in messages[:-1] if messages else []:
        history.append({"role": msg.role, "content": msg.content})
    return history


def count_tokens(text: str) -> int:
    """Best-effort token count.

    Uses ``tiktoken`` when available, otherwise falls back to a
    ``len(text) // 4`` heuristic (never returns 0 for non-empty text).
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4) if text else 0


def inject_system_into_history(
    history: list[dict[str, str]],
    system_prompt: str | None,
) -> list[dict[str, str]]:
    """Prepend a system message to the history if not already present.

    Returns a **new** list — never mutates the input.
    """
    if not system_prompt:
        return history
    if history and history[0]["role"] == "system":
        return history
    return [{"role": "system", "content": system_prompt}, *history]

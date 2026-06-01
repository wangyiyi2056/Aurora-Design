"""Ollama API compatibility layer for Aurora.

Provides a drop-in shim so that Ollama-aware clients (Open WebUI,
Continue, etc.) can talk to the Aurora RAG knowledge base.

Public API:
    - ``router`` — FastAPI router to include in the application
    - ``OllamaCompatConfig`` — configuration dataclass
    - ``get_config`` / ``set_config`` — config singleton accessors
    - Request/response Pydantic models
"""

from aurora_serve.ollama_compat.config import (
    OllamaCompatConfig,
    get_config,
    load_ollama_config,
    set_config,
)
from aurora_serve.ollama_compat.models import (
    OllamaChatRequest,
    OllamaChatResponse,
    OllamaGenerateRequest,
    OllamaGenerateResponse,
    OllamaMessage,
    OllamaModelDetails,
    OllamaModelInfo,
    OllamaRunningModelsResponse,
    OllamaShowRequest,
    OllamaShowResponse,
    OllamaTagsResponse,
    OllamaVersionResponse,
)
from aurora_serve.ollama_compat.routes import router

__all__ = [
    "OllamaChatRequest",
    "OllamaChatResponse",
    "OllamaCompatConfig",
    "OllamaGenerateRequest",
    "OllamaGenerateResponse",
    "OllamaMessage",
    "OllamaModelDetails",
    "OllamaModelInfo",
    "OllamaRunningModelsResponse",
    "OllamaShowRequest",
    "OllamaShowResponse",
    "OllamaTagsResponse",
    "OllamaVersionResponse",
    "get_config",
    "load_ollama_config",
    "router",
    "set_config",
]

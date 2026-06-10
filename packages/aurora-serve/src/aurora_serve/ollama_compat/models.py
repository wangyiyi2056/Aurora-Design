"""Ollama-compatible API request/response models.

Pydantic v2 models with ``frozen=True`` for immutability, matching the
Ollama REST API specification closely enough for Open WebUI and other
Ollama-aware clients.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Shared ──────────────────────────────────────────────────────────


class OllamaMessage(BaseModel):
    """A single message in an Ollama conversation."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


# ── Chat ────────────────────────────────────────────────────────────


class OllamaChatRequest(BaseModel):
    """Ollama-compatible chat request.

    Mirrors the ``POST /api/chat`` body accepted by the Ollama server.
    """

    model_config = ConfigDict(frozen=True)

    model: str = Field(default="aurora", description="Model name")
    messages: List[OllamaMessage] = Field(..., description="Conversation messages")
    stream: bool = Field(default=True, description="Stream the response")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Model options/parameters"
    )
    system: Optional[str] = Field(
        default=None, description="System prompt override"
    )


class OllamaChatResponse(BaseModel):
    """Non-streaming Ollama chat response."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(..., description="Model name that produced the response")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    message: OllamaMessage = Field(..., description="Assistant message")
    done: bool = Field(..., description="Whether generation is complete")
    total_duration: int = Field(default=0, description="Total wall-clock duration in nanoseconds")
    prompt_eval_count: int = Field(default=0, description="Approximate prompt token count")
    eval_count: int = Field(default=0, description="Approximate response token count")


# ── Generate ────────────────────────────────────────────────────────


class OllamaGenerateRequest(BaseModel):
    """Ollama-compatible text generation request.

    Mirrors the ``POST /api/generate`` body accepted by the Ollama server.
    Raw text completion — NOT routed through RAG.
    """

    model_config = ConfigDict(frozen=True)

    model: str = Field(default="aurora", description="Model name")
    prompt: str = Field(..., description="Generation prompt")
    system: Optional[str] = Field(
        default=None, description="System prompt override"
    )
    stream: bool = Field(default=False, description="Stream the response")
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Model options/parameters"
    )


class OllamaGenerateResponse(BaseModel):
    """Non-streaming Ollama generate response."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(..., description="Model name")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    response: str = Field(..., description="Generated text")
    done: bool = Field(..., description="Whether generation is complete")
    total_duration: int = Field(default=0, description="Total wall-clock duration in nanoseconds")
    prompt_eval_count: int = Field(default=0, description="Approximate prompt token count")
    eval_count: int = Field(default=0, description="Approximate response token count")


# ── Model Management ────────────────────────────────────────────────


class OllamaModelDetails(BaseModel):
    """Detailed metadata for a single model."""

    model_config = ConfigDict(frozen=True)

    parent_model: str = Field(default="", description="Parent model name")
    format: str = Field(default="aurora", description="Model format")
    family: str = Field(default="rag", description="Model family")
    families: List[str] = Field(default_factory=lambda: ["rag"], description="Model families")
    parameter_size: str = Field(default="N/A", description="Parameter size")
    quantization_level: str = Field(default="N/A", description="Quantization level")


class OllamaModelInfo(BaseModel):
    """A single model entry returned by ``/api/tags``."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Full model name (name:tag)")
    model: str = Field(..., description="Full model name (name:tag)")
    modified_at: str = Field(default="2024-01-01T00:00:00Z", description="Last modified timestamp")
    size: int = Field(default=0, description="Model size in bytes (0 for virtual)")
    digest: str = Field(default="sha256:aurora_rag_emulated", description="Model digest")
    details: OllamaModelDetails = Field(
        default_factory=OllamaModelDetails, description="Model details"
    )


class OllamaTagsResponse(BaseModel):
    """Response from ``GET /api/tags``."""

    model_config = ConfigDict(frozen=True)

    models: List[OllamaModelInfo] = Field(default_factory=list, description="Available models")


class OllamaShowRequest(BaseModel):
    """Request body for ``POST /api/show``."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Model name to show")


class OllamaShowResponse(BaseModel):
    """Response from ``POST /api/show``."""

    model_config = ConfigDict(frozen=True)

    license: str = Field(default="MIT", description="Model license")
    modelfile: str = Field(default="", description="Modelfile content")
    parameters: str = Field(default="", description="Model parameters")
    template: str = Field(default="", description="Prompt template")
    details: OllamaModelDetails = Field(
        default_factory=OllamaModelDetails, description="Model details"
    )


class OllamaVersionResponse(BaseModel):
    """Response from ``GET /api/version``."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(default="0.9.3", description="Simulated Ollama version")


class OllamaRunningModelsResponse(BaseModel):
    """Response from ``GET /api/ps``."""

    model_config = ConfigDict(frozen=True)

    models: List[OllamaModelInfo] = Field(
        default_factory=list, description="Currently loaded models"
    )

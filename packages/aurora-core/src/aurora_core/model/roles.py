"""LLM Role Registry for per-role model binding and concurrency isolation.

Each RAG operation (extraction, keyword extraction, query generation, VLM)
can be bound to a different LLM with independent concurrency limits.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional

from aurora_core.model.base import BaseLLM
from aurora_core.schema.model import LLMConfig

if TYPE_CHECKING:
    from aurora_core.model.registry import ModelRegistry

logger = logging.getLogger(__name__)


class LLMRole(str, Enum):
    """Roles that can be bound to specific LLMs."""

    EXTRACT = "extract"  # Entity/relation extraction
    KEYWORD = "keyword"  # Query keyword extraction
    QUERY = "query"  # Final RAG answer generation
    VLM = "vlm"  # Visual language model (multimodal)


@dataclass(frozen=True)
class RoleLLMConfig:
    """Configuration for a role-specific LLM binding.

    Attributes
    ----------
    model_name:
        Name of the registered LLM to use, or model identifier for creating a new one.
    model_type:
        Adapter type: ``openai``, ``anthropic``, ``google``, ``azure_openai``, ``ollama``.
    max_async:
        Maximum concurrent requests for this role.
    timeout:
        Request timeout in seconds.
    kwargs:
        Additional keyword arguments passed to the adapter constructor.
    """

    model_name: str
    model_type: str = "openai"
    max_async: int = 4
    timeout: int = 180
    kwargs: dict = field(default_factory=dict)


class LLMRoleRegistry:
    """Manages per-role LLM bindings with independent concurrency.

    By default, all roles fall back to the first registered LLM from the
    underlying :class:`ModelRegistry`. Use :meth:`update_role_config` to
    hot-swap a role to a different model at runtime.

    Parameters
    ----------
    model_registry:
        The underlying model registry that holds LLM instances.
    """

    def __init__(self, model_registry: ModelRegistry) -> None:
        self._model_registry = model_registry
        self._role_configs: Dict[LLMRole, RoleLLMConfig] = {}
        self._role_llms: Dict[LLMRole, BaseLLM] = {}
        self._semaphores: Dict[LLMRole, asyncio.Semaphore] = {
            role: asyncio.Semaphore(4) for role in LLMRole
        }
        self._lock = asyncio.Lock()

    def _get_default_ll(self) -> BaseLLM:
        """Return the first registered LLM from the model registry."""
        return self._model_registry.get_llm()

    async def get_llm(self, role: LLMRole) -> BaseLLM:
        """Get the LLM bound to a specific role.

        Falls back to the first registered LLM if no role-specific binding
        exists.

        Parameters
        ----------
        role:
            The LLM role to look up.

        Returns
        -------
        BaseLLM
            The LLM instance for this role.
        """
        async with self._lock:
            if role in self._role_llms:
                return self._role_llms[role]
        return self._get_default_ll()

    async def update_role_config(
        self, role: LLMRole, config: RoleLLMConfig
    ) -> None:
        """Hot-swap the LLM for a role at runtime.

        Creates a new LLM instance based on the config and replaces the
        old binding. Thread-safe via asyncio.Lock.

        Parameters
        ----------
        role:
            The role to update.
        config:
            The new role LLM configuration.
        """
        from aurora_core.model.adapter.anthropic_adapter import AnthropicLLM
        from aurora_core.model.adapter.azure_adapter import AzureOpenAILLM
        from aurora_core.model.adapter.google_adapter import GoogleLLM
        from aurora_core.model.adapter.ollama_adapter import OllamaLLM
        from aurora_core.model.adapter.openai_adapter import OpenAILLM

        adapter_map = {
            "openai": OpenAILLM,
            "anthropic": AnthropicLLM,
            "google": GoogleLLM,
            "azure_openai": AzureOpenAILLM,
            "ollama": OllamaLLM,
        }

        adapter_cls = adapter_map.get(config.model_type)
        if adapter_cls is None:
            raise ValueError(
                f"Unknown model_type '{config.model_type}'. "
                f"Supported: {list(adapter_map.keys())}"
            )

        llm_config = LLMConfig(
            model_name=config.model_name,
            model_type=config.model_type,
            max_tokens=config.kwargs.get("max_tokens"),
            temperature=config.kwargs.get("temperature", 0.7),
            api_base=config.kwargs.get("api_base"),
            api_key=config.kwargs.get("api_key"),
            extra=config.kwargs.get("extra", {}),
        )
        new_llm = adapter_cls(llm_config)
        new_semaphore = asyncio.Semaphore(config.max_async)

        async with self._lock:
            self._role_configs[role] = config
            self._role_llms[role] = new_llm
            self._semaphores[role] = new_semaphore

        logger.info(
            "Role '%s' updated: model=%s, max_async=%d",
            role.value,
            config.model_name,
            config.max_async,
        )

    async def get_role_config(self, role: LLMRole) -> Optional[RoleLLMConfig]:
        """Return the configuration for a role, or ``None`` if using default.

        Parameters
        ----------
        role:
            The role to query.

        Returns
        -------
        RoleLLMConfig | None
            The role-specific config, or ``None`` if falling back to default.
        """
        async with self._lock:
            return self._role_configs.get(role)

    async def get_queue_status(self) -> Dict[str, dict]:
        """Return queue/semaphore status for each role.

        Returns
        -------
        dict
            Mapping of role name to status dict with keys:
            ``model_name``, ``max_async``, ``current_available``.
        """
        async with self._lock:
            status: Dict[str, dict] = {}
            for role in LLMRole:
                config = self._role_configs.get(role)
                semaphore = self._semaphores[role]
                llm = self._role_llms.get(role)

                if llm is not None:
                    model_name = llm.config.model_name
                elif config is not None:
                    model_name = config.model_name
                else:
                    try:
                        default_llm = self._get_default_ll()
                        model_name = default_llm.config.model_name
                    except RuntimeError:
                        model_name = "<none>"

                status[role.value] = {
                    "model_name": model_name,
                    "max_async": config.max_async if config else 4,
                    "current_available": semaphore._value,
                }
            return status

    def get_semaphore(self, role: LLMRole) -> asyncio.Semaphore:
        """Get the concurrency semaphore for a role.

        This method is synchronous because semaphores are not replaced
        frequently and callers need quick access in hot paths.

        Parameters
        ----------
        role:
            The role to get the semaphore for.

        Returns
        -------
        asyncio.Semaphore
            The semaphore controlling concurrency for this role.
        """
        return self._semaphores.get(role, asyncio.Semaphore(4))

from typing import Dict, Optional

from aurora_core.model.base import BaseEmbeddings, BaseLLM


class ModelRegistry:
    def __init__(self):
        self._llms: Dict[str, BaseLLM] = {}
        self._embeddings: Dict[str, BaseEmbeddings] = {}
        self._default_llm_name: Optional[str] = None
        self._default_embeddings_name: Optional[str] = None

    def register_llm(
        self, name: str, instance: BaseLLM, *, is_default: bool = False
    ) -> None:
        self._llms[name] = instance
        if is_default:
            self._default_llm_name = name

    def unregister_llm(self, name: str) -> None:
        self._llms.pop(name, None)
        if self._default_llm_name == name:
            self._default_llm_name = None

    def set_default_llm(self, name: str) -> None:
        if name not in self._llms:
            raise KeyError(f"LLM '{name}' not found")
        self._default_llm_name = name

    def get_llm(self, name: Optional[str] = None) -> BaseLLM:
        if name is None:
            if not self._llms:
                raise RuntimeError("No LLM registered")
            if self._default_llm_name in self._llms:
                return self._llms[self._default_llm_name]
            return next(iter(self._llms.values()))
        if name not in self._llms:
            raise KeyError(f"LLM '{name}' not found")
        return self._llms[name]

    def register_embeddings(
        self, name: str, instance: BaseEmbeddings, *, is_default: bool = False
    ) -> None:
        self._embeddings[name] = instance
        if is_default:
            self._default_embeddings_name = name

    def unregister_embeddings(self, name: str) -> None:
        self._embeddings.pop(name, None)
        if self._default_embeddings_name == name:
            self._default_embeddings_name = None

    def set_default_embeddings(self, name: str) -> None:
        if name not in self._embeddings:
            raise KeyError(f"Embeddings '{name}' not found")
        self._default_embeddings_name = name

    def get_embeddings(self, name: Optional[str] = None) -> BaseEmbeddings:
        if name is None:
            if not self._embeddings:
                raise RuntimeError("No Embeddings registered")
            if self._default_embeddings_name in self._embeddings:
                return self._embeddings[self._default_embeddings_name]
            return next(iter(self._embeddings.values()))
        if name not in self._embeddings:
            raise KeyError(f"Embeddings '{name}' not found")
        return self._embeddings[name]

    def has_llm(self) -> bool:
        return bool(self._llms)

    def has_embeddings(self) -> bool:
        return bool(self._embeddings)

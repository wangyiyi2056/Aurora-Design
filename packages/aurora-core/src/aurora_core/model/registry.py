from typing import Dict, Optional

from aurora_core.model.base import BaseEmbeddings, BaseLLM


class ModelRegistry:
    def __init__(self):
        self._llms: Dict[str, BaseLLM] = {}
        self._embeddings: Dict[str, BaseEmbeddings] = {}

    def register_llm(self, name: str, instance: BaseLLM) -> None:
        self._llms[name] = instance

    def unregister_llm(self, name: str) -> None:
        self._llms.pop(name, None)

    def get_llm(self, name: Optional[str] = None) -> BaseLLM:
        if name is None:
            if not self._llms:
                raise RuntimeError("No LLM registered")
            return next(iter(self._llms.values()))
        if name not in self._llms:
            raise KeyError(f"LLM '{name}' not found")
        return self._llms[name]

    def register_embeddings(self, name: str, instance: BaseEmbeddings) -> None:
        self._embeddings[name] = instance

    def unregister_embeddings(self, name: str) -> None:
        self._embeddings.pop(name, None)

    def get_embeddings(self, name: Optional[str] = None) -> BaseEmbeddings:
        if name is None:
            if not self._embeddings:
                raise RuntimeError("No Embeddings registered")
            return next(iter(self._embeddings.values()))
        if name not in self._embeddings:
            raise KeyError(f"Embeddings '{name}' not found")
        return self._embeddings[name]

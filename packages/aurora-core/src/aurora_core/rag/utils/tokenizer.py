"""Token counting via tiktoken — migrated from LightRAG ``utils.py``."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"


class TiktokenTokenizer:
    """Thin wrapper around ``tiktoken`` for counting tokens.

    Mirrors the LightRAG ``TiktokenTokenizer`` interface.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._encoder = None

    @property
    def encoder(self):
        if self._encoder is None:
            try:
                import tiktoken

                try:
                    self._encoder = tiktoken.encoding_for_model(self._model_name)
                except KeyError:
                    self._encoder = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                logger.warning(
                    "tiktoken not installed — falling back to char-based estimation"
                )
                self._encoder = None
        return self._encoder

    def encode(self, text: str) -> list[int]:
        """Encode *text* into token ids."""
        if self.encoder is None:
            return list(text.encode("utf-8"))
        return self.encoder.encode(text, disallowed_special=())

    def decode(self, tokens: list[int]) -> str:
        """Decode token ids back to text."""
        if self.encoder is None:
            return bytes(tokens).decode("utf-8", errors="replace")
        return self.encoder.decode(tokens)

    def count(self, text: str) -> int:
        """Return the number of tokens in *text*."""
        return len(self.encode(text))

    def truncate(self, text: str, max_tokens: int) -> str:
        """Truncate *text* to at most *max_tokens* tokens."""
        tokens = self.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.decode(tokens[:max_tokens])


@lru_cache(maxsize=1)
def _default_tokenizer() -> TiktokenTokenizer:
    return TiktokenTokenizer()


def count_tokens(text: str, model_name: Optional[str] = None) -> int:
    """Convenience function: count tokens in *text*.

    Uses a cached default tokenizer when *model_name* is ``None``.
    """
    if model_name is not None:
        return TiktokenTokenizer(model_name).count(text)
    return _default_tokenizer().count(text)


def truncate_text(text: str, max_tokens: int, model_name: Optional[str] = None) -> str:
    """Convenience function: truncate *text* to *max_tokens*."""
    if model_name is not None:
        return TiktokenTokenizer(model_name).truncate(text, max_tokens)
    return _default_tokenizer().truncate(text, max_tokens)

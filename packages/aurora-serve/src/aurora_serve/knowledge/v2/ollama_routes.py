"""Backward-compatible re-export of the Ollama compat layer.

The canonical implementation now lives in
``aurora_serve.ollama_compat``.  This module re-exports the router
so that any existing imports continue to work.
"""

from aurora_serve.ollama_compat import router  # noqa: F401

__all__ = ["router"]

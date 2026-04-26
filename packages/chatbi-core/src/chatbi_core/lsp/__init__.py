"""LSP code intelligence using Jedi for Python static analysis.

Provides go-to-definition, find-references, hover, document symbols,
and workspace symbol search without requiring a running language server.
"""

from chatbi_core.lsp.handler import (
    LSPHandler,
    get_lsp_handler,
    execute_lsp,
)

__all__ = [
    "LSPHandler",
    "get_lsp_handler",
    "execute_lsp",
]

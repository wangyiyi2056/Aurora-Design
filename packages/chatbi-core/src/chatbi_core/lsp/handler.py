"""LSP handler using Jedi for Python code intelligence.

Provides go-to-definition, find-references, hover info, and symbol search
without requiring a running language server process.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class LSPHandler:
    """Handles LSP operations using static analysis and Jedi.

    Usage::

        handler = LSPHandler()
        result = handler.execute("goToDefinition", file_path="src/main.py", line=10, character=5)
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._jedi_available: Optional[bool] = None

    def _check_jedi(self) -> bool:
        if self._jedi_available is not None:
            return self._jedi_available
        try:
            import jedi  # noqa: F401
            self._jedi_available = True
        except ImportError:
            self._jedi_available = False
        return self._jedi_available

    def execute(
        self,
        operation: str,
        file_path: str = "",
        line: int = 0,
        character: int = 0,
        query: str = "",
    ) -> str:
        if not self._check_jedi():
            return (
                "[LSP requires jedi package. Install with: pip install jedi]\n"
                "Jedi provides static analysis for Python code intelligence."
            )

        import jedi

        path = Path(file_path) if file_path else None
        if path and not path.is_absolute():
            path = self.project_root / path

        if operation == "goToDefinition" and path and path.exists():
            return self._go_to_definition(jedi, path, line, character)
        elif operation == "findReferences" and path and path.exists():
            return self._find_references(jedi, path, line, character)
        elif operation == "hover" and path and path.exists():
            return self._hover(jedi, path, line, character)
        elif operation == "documentSymbol" and path and path.exists():
            return self._document_symbols(jedi, path)
        elif operation == "workspaceSymbol" and query:
            return self._workspace_symbols(jedi, query)
        elif operation == "goToImplementation" and path and path.exists():
            return self._go_to_implementation(jedi, path, line, character)
        else:
            return f"[LSP {operation}: file not found or invalid parameters]"

    def _go_to_definition(self, jedi, path: Path, line: int, character: int) -> str:
        try:
            source = path.read_text(encoding="utf-8")
            script = jedi.Script(source, path=str(path))
            names = script.goto(line=line, column=character)
            if not names:
                return f"[No definition found at {path}:{line}:{character}]"
            results = []
            for n in names:
                loc = f"{n.module_path}:{n.line}:{n.column}" if n.module_path else "built-in"
                results.append(f"{n.full_name} -> {loc}\n{n.get_line_code()}")
            return "\n\n".join(results)
        except Exception as e:
            return f"[LSP goToDefinition error: {e}]"

    def _find_references(self, jedi, path: Path, line: int, character: int) -> str:
        try:
            source = path.read_text(encoding="utf-8")
            script = jedi.Script(source, path=str(path))
            names = script.get_references(line=line, column=character)
            if not names:
                return f"[No references found at {path}:{line}:{character}]"
            results = [f"References to '{names[0].full_name}':"]
            for n in names[:50]:
                loc = f"{n.module_path}:{n.line}" if n.module_path else "built-in"
                results.append(f"  {loc}: {n.get_line_code()}")
            return "\n".join(results)
        except Exception as e:
            return f"[LSP findReferences error: {e}]"

    def _hover(self, jedi, path: Path, line: int, character: int) -> str:
        try:
            source = path.read_text(encoding="utf-8")
            script = jedi.Script(source, path=str(path))
            names = script.help(line=line, column=character)
            if not names:
                return f"[No hover info at {path}:{line}:{character}]"
            results = []
            for n in names:
                results.append(f"**{n.full_name}**\n{n.docstring() if n.docstring() else 'No documentation.'}")
            return "\n\n---\n\n".join(results)
        except Exception as e:
            return f"[LSP hover error: {e}]"

    def _document_symbols(self, jedi, path: Path) -> str:
        try:
            source = path.read_text(encoding="utf-8")
            script = jedi.Script(source, path=str(path))
            names = script.get_names()
            if not names:
                return f"[No symbols found in {path}]"
            results = [f"Symbols in {path.name}:"]
            for n in names:
                results.append(f"  {n.type:12} {n.full_name:40} line {n.line}")
            return "\n".join(results)
        except Exception as e:
            return f"[LSP documentSymbol error: {e}]"

    def _workspace_symbols(self, jedi, query: str) -> str:
        try:
            results = []
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                for f in files:
                    if f.endswith(".py"):
                        fpath = os.path.join(root, f)
                        try:
                            source = Path(fpath).read_text(encoding="utf-8")
                            script = jedi.Script(source, path=fpath)
                            names = script.search(query)
                            for n in names[:5]:
                                results.append(f"{n.type} {n.full_name} — {fpath}:{n.line}")
                        except Exception:
                            continue
                if len(results) >= 20:
                    break
            if not results:
                return f"[No symbols matching '{query}' found]"
            header = f"Workspace symbols matching '{query}':"
            return header + "\n" + "\n".join(results[:20])
        except Exception as e:
            return f"[LSP workspaceSymbol error: {e}]"

    def _go_to_implementation(self, jedi, path: Path, line: int, character: int) -> str:
        try:
            source = path.read_text(encoding="utf-8")
            script = jedi.Script(source, path=str(path))
            names = script.goto(line=line, column=character)
            if not names:
                return f"[No implementation found at {path}:{line}:{character}]"
            results = []
            for n in names:
                # Try to find subclass implementations
                results.append(f"{n.type} {n.full_name} -> {n.module_path}:{n.line}")
            return "\n".join(results)
        except Exception as e:
            return f"[LSP goToImplementation error: {e}]"


# Global handler instance
_default_handler: Optional[LSPHandler] = None


def get_lsp_handler(project_root: Optional[str] = None) -> LSPHandler:
    global _default_handler
    if _default_handler is None or project_root:
        _default_handler = LSPHandler(project_root=project_root)
    return _default_handler


def execute_lsp(
    operation: str,
    file_path: str = "",
    line: int = 0,
    character: int = 0,
    query: str = "",
    project_root: Optional[str] = None,
) -> str:
    """Execute an LSP operation using the default handler."""
    handler = get_lsp_handler(project_root)
    return handler.execute(operation, file_path, line, character, query)

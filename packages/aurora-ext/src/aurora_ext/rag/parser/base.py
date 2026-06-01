"""Abstract base parser and result dataclass.

Migrated from LightRAG ``parser/`` interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing a single document.

    Attributes
    ----------
    text:
        Extracted plain text.
    file_path:
        Original file path.
    file_type:
        File extension (lowercased, without dot).
    metadata:
        Arbitrary metadata extracted during parsing (page count,
        sheet names, etc.).
    """

    text: str
    file_path: str
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract document parser.

    Subclasses must implement :meth:`parse` for their specific file
    format.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return the set of file extensions this parser handles (lowercase, no dot)."""

    @abstractmethod
    async def parse(self, file_path: str | Path, **kwargs: Any) -> ParseResult:
        """Parse the file at *file_path* and return extracted text.

        Raises
        ------
        ValueError
            When the file cannot be parsed.
        """

    def can_handle(self, file_path: str | Path) -> bool:
        """Check whether this parser supports the file's extension."""
        ext = Path(file_path).suffix.lstrip(".").lower()
        return ext in self.supported_extensions

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, List

from aurora_ext.rag.knowledge.base import BaseKnowledge, Document

logger = logging.getLogger(__name__)


class FileKnowledge(BaseKnowledge):
    """Load a single file into a Document with full citation metadata.

    Uses the parser routing system for PDFs and other non-text formats.
    Falls back to plain text reading for unsupported extensions.
    """

    def __init__(self, file_path: str):
        self.file_path = str(Path(file_path))

    def load(self) -> List[Document]:
        path = Path(self.file_path)

        # Try parser routing system first (handles PDF, DOCX, XLSX …)
        try:
            from aurora_ext.rag.parser.routing import parse_file

            # parse_file is async; bridge into sync context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already inside an event loop — create a new one in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, parse_file(path))
                    result = future.result()
            else:
                result = asyncio.run(parse_file(path))

            metadata: dict[str, Any] = {
                **result.metadata,
                "source": str(path),
                "file_path": str(path),
                "file_type": result.file_type,
            }
            return [Document(content=result.text, metadata=metadata)]

        except Exception as exc:
            logger.debug("Parser routing failed for %s, falling back to text read: %s", path, exc)

        # Fallback: plain text
        text = path.read_text(encoding="utf-8")
        return [Document(content=text, metadata={
            "source": str(path),
            "file_path": str(path),
        })]


class KnowledgeFactory:
    @staticmethod
    def from_file_path(file_path: str) -> BaseKnowledge:
        return FileKnowledge(file_path)

"""MinerU parser — GPU-accelerated document parsing.

MinerU (``magic-pdf``) provides high-quality text extraction for PDFs
and office documents via GPU-accelerated layout analysis and OCR.

Two invocation modes:

1. **Local SDK** — ``magic-pdf`` installed in-process (requires GPU).
2. **Remote HTTP API** — when ``MINERU_API_URL`` is set, delegates to a
   running MinerU service (no local GPU needed).

The parser degrades gracefully: if neither the SDK nor the API URL is
available, :meth:`parse` raises ``ValueError`` with installation hints.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from aurora_ext.rag.parser.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)

_EXTENSIONS = {
    "pdf",
    "doc", "docx",
    "ppt", "pptx",
    "xls", "xlsx",
    "png", "jpg", "jpeg", "webp", "gif", "bmp",
}

_DEFAULT_MAX_PARALLEL = 1


class MinerUParser(BaseParser):
    """GPU-accelerated document parser powered by MinerU / magic-pdf.

    Configuration
    -------------
    ``MINERU_API_URL``
        If set, use the remote HTTP API instead of the local SDK.
    ``MINERU_MAX_PARALLEL``
        Maximum concurrent parse jobs (default ``1`` — GPU-bound).
    """

    def __init__(self, *, max_parallel: int | None = None) -> None:
        self._max_parallel = max_parallel or int(
            os.environ.get("MINERU_MAX_PARALLEL", str(_DEFAULT_MAX_PARALLEL))
        )
        self._semaphore = asyncio.Semaphore(self._max_parallel)

    @property
    def supported_extensions(self) -> set[str]:
        return _EXTENSIONS

    # ------------------------------------------------------------------
    # Availability helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _api_url() -> str | None:
        """Return the remote API URL if configured, else ``None``."""
        return os.environ.get("MINERU_API_URL")

    @staticmethod
    def _sdk_available() -> bool:
        """Check whether ``magic_pdf`` SDK is importable."""
        try:
            import magic_pdf  # noqa: F401
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Return ``True`` when at least one invocation mode is usable."""
        return self._api_url() is not None or self._sdk_available()

    # ------------------------------------------------------------------
    # Core parse
    # ------------------------------------------------------------------

    async def parse(self, file_path: str | Path, **kwargs: Any) -> ParseResult:
        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()
        if ext not in _EXTENSIONS:
            raise ValueError(
                f"MinerU does not support '.{ext}'. "
                f"Supported: {sorted(_EXTENSIONS)}"
            )

        async with self._semaphore:
            api_url = self._api_url()
            if api_url:
                return await self._parse_via_api(path, api_url, **kwargs)
            if self._sdk_available():
                return await self._parse_via_sdk(path, **kwargs)

            raise ValueError(
                "MinerU is not available. Install the SDK "
                "(`pip install magic-pdf`) or set MINERU_API_URL "
                "to a running MinerU service."
            )

    # ------------------------------------------------------------------
    # SDK mode
    # ------------------------------------------------------------------

    async def _parse_via_sdk(self, path: Path, **kwargs: Any) -> ParseResult:
        """Parse using the local ``magic_pdf`` SDK (offloaded to a thread)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sdk_extract, path, kwargs)

    @staticmethod
    def _sdk_extract(path: Path, kwargs: dict[str, Any]) -> ParseResult:
        """Synchronous SDK extraction — runs in a worker thread."""
        from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader  # type: ignore[import-untyped]
        from magic_pdf.pipe.UNIPipe import UNIPipe  # type: ignore[import-untyped]

        image_writer = FileBasedDataWriter(str(path.parent))
        model_json = kwargs.get("model_json")

        reader = FileBasedDataReader("")
        raw_bytes = reader.read(str(path))

        pipe = UNIPipe(
            raw_bytes,
            image_writer=image_writer,
            ocr=True,
            model_json=model_json,
        )
        pipe.pipe_classify()
        pipe.pipe_analyze()
        pipe.pipe_parse()

        content: str = pipe.pipe_mk_uni_format(
            str(path.parent),
            drop_mode="none",
        )
        if not content:
            content = pipe.pipe_mk_markdown(
                image_writer,
                drop_mode="none",
            ) or ""

        return ParseResult(
            text=content.strip(),
            file_path=str(path),
            file_type=path.suffix.lstrip(".").lower(),
            metadata={
                "parser_engine": "mineru_sdk",
                "char_count": len(content),
            },
        )

    # ------------------------------------------------------------------
    # Remote API mode
    # ------------------------------------------------------------------

    async def _parse_via_api(
        self, path: Path, api_url: str, **kwargs: Any
    ) -> ParseResult:
        """Parse by uploading the file to a remote MinerU HTTP service."""
        import aiohttp

        timeout = aiohttp.ClientTimeout(
            total=kwargs.get("timeout", 600),
        )

        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = aiohttp.FormData()
            data.add_field(
                "file",
                path.read_bytes(),
                filename=path.name,
                content_type="application/octet-stream",
            )

            ocr = str(kwargs.get("ocr", "true")).lower()
            data.add_field("ocr", ocr)

            async with session.post(f"{api_url.rstrip('/')}/parse", data=data) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise ValueError(
                        f"MinerU API returned {resp.status}: {body[:500]}"
                    )
                result = await resp.json()

        text = result.get("text", "")
        blocks = result.get("blocks", [])
        metadata = {
            "parser_engine": "mineru_api",
            "char_count": len(text),
            "block_count": len(blocks),
        }

        return ParseResult(
            text=text.strip(),
            file_path=str(path),
            file_type=path.suffix.lstrip(".").lower(),
            metadata=metadata,
        )

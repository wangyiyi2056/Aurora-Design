"""Tests for the LangChain adapter module.

Tests cover:
- wrap_llm function for converting Aurora LLM to LangChain
- wrap_embeddings function for converting Aurora Embeddings to LangChain
- Async-to-sync bridging (_run_async)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_aurora_llm():
    """Mock Aurora BaseLLM."""
    llm = Mock()
    llm.achat = AsyncMock(return_value=Mock(text="Test response"))
    return llm


@pytest.fixture
def mock_aurora_embeddings():
    """Mock Aurora BaseEmbeddings."""
    embeddings = Mock()
    embeddings.aembed = AsyncMock(
        return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    )
    return embeddings


# ── Tests for _run_async ────────────────────────────────────────────────────


class TestRunAsync:
    """Tests for the _run_async helper function."""

    def test_run_async_no_loop(self):
        """Test _run_async when no event loop is running."""
        from aurora_ext.rag.evaluation.langchain_adapter import _run_async

        async def sample_coro():
            return "result"

        result = _run_async(sample_coro())
        assert result == "result"

    def test_run_async_with_loop(self):
        """Test _run_async when an event loop is already running."""
        from aurora_ext.rag.evaluation.langchain_adapter import _run_async

        async def sample_coro():
            return "result"

        async def outer():
            # Inside a running event loop
            result = _run_async(sample_coro())
            return result

        # Run the outer coroutine
        result = asyncio.run(outer())
        assert result == "result"


# ── Tests for wrap_llm ──────────────────────────────────────────────────────


class TestWrapLLM:
    """Tests for wrap_llm function."""

    def test_wrap_llm_creates_chat_model(self, mock_aurora_llm):
        """Test that wrap_llm creates a LangChain BaseChatModel."""
        try:
            from aurora_ext.rag.evaluation.langchain_adapter import wrap_llm

            lc_llm = wrap_llm(mock_aurora_llm)
            assert lc_llm is not None
            assert hasattr(lc_llm, "_generate")
            assert hasattr(lc_llm, "_agenerate")
        except ImportError:
            pytest.skip("langchain_core not installed")

    def test_wrap_llm_type(self, mock_aurora_llm):
        """Test that wrapped LLM has correct type."""
        try:
            from aurora_ext.rag.evaluation.langchain_adapter import wrap_llm

            lc_llm = wrap_llm(mock_aurora_llm)
            assert lc_llm._llm_type == "aurora-chat"
        except ImportError:
            pytest.skip("langchain_core not installed")

    def test_wrap_llm_generate(self, mock_aurora_llm):
        """Test that wrapped LLM can generate responses."""
        try:
            from langchain_core.messages import HumanMessage

            from aurora_ext.rag.evaluation.langchain_adapter import wrap_llm

            lc_llm = wrap_llm(mock_aurora_llm)
            messages = [HumanMessage(content="Hello")]
            result = lc_llm._generate(messages)

            assert result is not None
            assert len(result.generations) == 1
            assert result.generations[0].message.content == "Test response"
        except ImportError:
            pytest.skip("langchain_core not installed")

    def test_wrap_llm_message_conversion(self, mock_aurora_llm):
        """Test message type conversion from LangChain to Aurora."""
        try:
            from langchain_core.messages import AIMessage, HumanMessage

            from aurora_ext.rag.evaluation.langchain_adapter import wrap_llm

            lc_llm = wrap_llm(mock_aurora_llm)

            # Test with different message types
            messages = [
                HumanMessage(content="User message"),
                AIMessage(content="AI message"),
            ]

            result = lc_llm._generate(messages)
            assert result is not None

            # Verify achat was called
            assert mock_aurora_llm.achat.called
        except ImportError:
            pytest.skip("langchain_core not installed")


# ── Tests for wrap_embeddings ───────────────────────────────────────────────


class TestWrapEmbeddings:
    """Tests for wrap_embeddings function."""

    def test_wrap_embeddings_creates_embeddings(self, mock_aurora_embeddings):
        """Test that wrap_embeddings creates a LangChain Embeddings."""
        try:
            from aurora_ext.rag.evaluation.langchain_adapter import (
                wrap_embeddings,
            )

            lc_embeddings = wrap_embeddings(mock_aurora_embeddings)
            assert lc_embeddings is not None
            assert hasattr(lc_embeddings, "embed_documents")
            assert hasattr(lc_embeddings, "embed_query")
        except ImportError:
            pytest.skip("langchain_core not installed")

    def test_wrap_embeddings_embed_documents(
        self, mock_aurora_embeddings
    ):
        """Test embedding multiple documents."""
        try:
            from aurora_ext.rag.evaluation.langchain_adapter import (
                wrap_embeddings,
            )

            lc_embeddings = wrap_embeddings(mock_aurora_embeddings)
            texts = ["First document", "Second document"]
            result = lc_embeddings.embed_documents(texts)

            assert result is not None
            assert len(result) == 2
            assert isinstance(result[0], list)
            assert len(result[0]) == 3  # [0.1, 0.2, 0.3]

            # Verify aembed was called
            assert mock_aurora_embeddings.aembed.called
        except ImportError:
            pytest.skip("langchain_core not installed")

    def test_wrap_embeddings_embed_query(self, mock_aurora_embeddings):
        """Test embedding a single query."""
        try:
            from aurora_ext.rag.evaluation.langchain_adapter import (
                wrap_embeddings,
            )

            lc_embeddings = wrap_embeddings(mock_aurora_embeddings)
            text = "Query text"
            result = lc_embeddings.embed_query(text)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) == 3  # First embedding [0.1, 0.2, 0.3]

            # Verify aembed was called
            assert mock_aurora_embeddings.aembed.called
        except ImportError:
            pytest.skip("langchain_core not installed")


# ── Integration Tests ───────────────────────────────────────────────────────


class TestLangChainAdapterIntegration:
    """Integration tests for the LangChain adapter."""

    def test_full_llm_flow(self, mock_aurora_llm):
        """Test complete LLM flow from LangChain to Aurora."""
        try:
            from langchain_core.messages import HumanMessage

            from aurora_ext.rag.evaluation.langchain_adapter import wrap_llm

            lc_llm = wrap_llm(mock_aurora_llm)

            # Simulate a RAGAS-like call
            messages = [HumanMessage(content="What is AI?")]
            result = lc_llm._generate(messages)

            assert result is not None
            assert len(result.generations) > 0
            assert result.generations[0].message.content == "Test response"
        except ImportError:
            pytest.skip("langchain_core not installed")

    def test_full_embeddings_flow(self, mock_aurora_embeddings):
        """Test complete embeddings flow from LangChain to Aurora."""
        try:
            from aurora_ext.rag.evaluation.langchain_adapter import (
                wrap_embeddings,
            )

            lc_embeddings = wrap_embeddings(mock_aurora_embeddings)

            # Simulate a RAGAS-like call
            docs = ["Document 1", "Document 2"]
            doc_embeddings = lc_embeddings.embed_documents(docs)
            query_embedding = lc_embeddings.embed_query("Query")

            assert len(doc_embeddings) == 2
            assert len(query_embedding) > 0
        except ImportError:
            pytest.skip("langchain_core not installed")

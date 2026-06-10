"""LangChain adapters — bridge Aurora LLM/Embeddings to LangChain interfaces.

RAGAS requires LangChain ``BaseChatModel`` and ``Embeddings`` as its judge
LLM and embedding function.  This module provides thin async-to-sync
wrappers so the existing Aurora ``BaseLLM`` and ``BaseEmbeddings`` can be
passed directly to RAGAS without duplicating model configuration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a sync context.

    If an event loop is already running (e.g. inside FastAPI), a new
    thread is spawned to avoid ``RuntimeError: This event loop is
    already running``.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None or not loop.is_running():
        return asyncio.run(coro)

    # Already inside a running loop — run in a separate thread
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def wrap_llm(aurora_llm: Any) -> Any:
    """Wrap an Aurora ``BaseLLM`` as a LangChain ``BaseChatModel``.

    Returns a ``ChatAurora`` instance that RAGAS can use as a judge LLM.

    Raises:
        ImportError: If ``langchain_core`` is not installed.
    """
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class ChatAurora(BaseChatModel):
        """LangChain ``BaseChatModel`` backed by an Aurora ``BaseLLM``."""

        aurora_llm: Any = None

        def __init__(self, llm: Any) -> None:
            super().__init__(aurora_llm=llm)

        @property
        def _llm_type(self) -> str:
            return "aurora-chat"

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
            from aurora_core.schema.message import Message

            aurora_messages: list[Message] = []
            for msg in messages:
                role = "user"
                if isinstance(msg, AIMessage):
                    role = "assistant"
                elif isinstance(msg, HumanMessage):
                    role = "user"
                elif hasattr(msg, "type"):
                    role = {"ai": "assistant", "human": "user"}.get(
                        msg.type, "user"
                    )
                aurora_messages.append(
                    Message(role=role, content=msg.content)
                )

            output = _run_async(self.aurora_llm.achat(aurora_messages))
            text = output.text if hasattr(output, "text") else str(output)

            return ChatResult(
                generations=[
                    ChatGeneration(message=AIMessage(content=text))
                ]
            )

        async def _agenerate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[Any] = None,
            **kwargs: Any,
        ) -> ChatResult:
            return self._generate(messages, stop=stop, **kwargs)

    return ChatAurora(aurora_llm)


def wrap_embeddings(aurora_embeddings: Any) -> Any:
    """Wrap an Aurora ``BaseEmbeddings`` as a LangChain ``Embeddings``.

    Returns an ``AuroraEmbeddings`` instance that RAGAS can use.

    Raises:
        ImportError: If ``langchain_core`` is not installed.
    """
    from langchain_core.embeddings import Embeddings as LCEmbeddings

    class AuroraEmbeddings(LCEmbeddings):
        """LangChain ``Embeddings`` backed by an Aurora ``BaseEmbeddings``."""

        aurora_embeddings: Any = None

        def __init__(self, emb: Any) -> None:
            super().__init__()
            self.aurora_embeddings = emb

        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return _run_async(self.aurora_embeddings.aembed(texts))

        def embed_query(self, text: str) -> List[float]:
            results = _run_async(self.aurora_embeddings.aembed([text]))
            return results[0]

    return AuroraEmbeddings(aurora_embeddings)

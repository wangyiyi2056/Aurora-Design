"""Example: Using the Reranker in Aurora RAG Pipeline.

This example demonstrates various ways to use the reranker module
in your RAG (Retrieval-Augmented Generation) pipeline.
"""

import asyncio

from aurora_ext.rag.retrieval import (
    AliyunReranker,
    CohereReranker,
    JinaReranker,
    QueryEngine,
    QueryMode,
    QueryParam,
    RerankerConfig,
    RerankOptions,
    RobustReranker,
    VLLMReranker,
    create_reranker,
)


# ── Example 1: Basic Cohere Reranker ─────────────────────────────


async def example_basic_cohere():
    """Basic usage of Cohere reranker."""
    # Initialize reranker
    reranker = CohereReranker(
        api_key="your-cohere-api-key",
        model="rerank-multilingual-v3.0"
    )

    # Sample query and documents
    query = "What is machine learning?"
    documents = [
        "Machine learning is a subset of artificial intelligence.",
        "Python is a popular programming language.",
        "Deep learning uses neural networks with many layers.",
        "Supervised learning requires labeled training data.",
    ]

    # Rerank documents
    results = await reranker.rerank(
        query=query,
        documents=documents,
        top_n=3
    )

    # Print results
    print(f"\nQuery: {query}\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result.score:.3f}")
        print(f"   Document: {result.content[:100]}...\n")


# ── Example 2: Configuration-Based Setup ─────────────────────────


async def example_config_based():
    """Load reranker from TOML configuration."""
    # Simulate loading from TOML file
    config_dict = {
        "reranker": {
            "enabled": True,
            "type": "cohere",
            "api_key": "your-api-key",
            "api_base": "https://api.cohere.ai/v1",
            "model": "rerank-multilingual-v3.0",
            "top_k": 10,
            "timeout": 30,
            "enable_chunking": False,
            "min_score": 0.0,
        }
    }

    # Load configuration
    config = RerankerConfig.from_toml(config_dict)

    # Create reranker via factory
    reranker = create_reranker(config)

    if reranker:
        print(f"Created reranker: {type(reranker).__name__}")
        print(f"Type: {config.type}")
        print(f"Model: {config.model}")


# ── Example 3: Robust Reranker with Error Handling ───────────────


async def example_robust_reranker():
    """Use RobustReranker for production-grade error handling."""
    # Base reranker
    base_reranker = CohereReranker(api_key="your-api-key")

    # Wrap with robust error handling
    reranker = RobustReranker(
        base_reranker,
        fallback_to_original=True,  # Return original order on failure
        circuit_breaker_threshold=5,  # Open circuit after 5 failures
        circuit_breaker_timeout=60.0  # Retry after 60 seconds
    )

    query = "What is machine learning?"
    documents = [
        "Machine learning is AI subset.",
        "Python programming language.",
        "Neural networks for deep learning.",
    ]

    # Even if API fails, returns original order
    results = await reranker.rerank(query, documents, top_n=3)

    print(f"\nGot {len(results)} results (with fallback)")


# ── Example 4: Long Document Chunking ────────────────────────────


async def example_chunking():
    """Use document chunking for long texts."""
    options = RerankOptions(
        enable_chunking=True,
        max_tokens_per_doc=2048,  # Split documents > 2048 tokens
        score_aggregation="max",  # Use highest chunk score
        min_score=0.5,
    )

    reranker = AliyunReranker(
        api_key="your-dashscope-key",
        model="gte-rerank-v2",
        options=options,
    )

    # Long document
    long_document = " ".join(["Machine learning concepts"] * 1000)

    query = "What is machine learning?"
    documents = [long_document, "Short document about ML"]

    results = await reranker.rerank(query, documents, top_n=2)

    print(f"\nReranked with chunking: {len(results)} results")


# ── Example 5: vLLM Self-Hosted Reranker ─────────────────────────


async def example_vllm():
    """Use vLLM for self-hosted reranking."""
    reranker = VLLMReranker(
        api_key="",  # Usually empty for local deployments
        model="BAAI/bge-reranker-v2-m3",
        endpoint="http://localhost:8000/v1/rerank",
        timeout=30.0,
    )

    query = "What is machine learning?"
    documents = [
        "Machine learning is a subset of AI.",
        "Deep learning uses neural networks.",
    ]

    results = await reranker.rerank(query, documents, top_n=2)

    print(f"\nvLLM reranked: {len(results)} results")


# ── Example 6: Integration with QueryEngine ──────────────────────


async def example_query_engine_integration():
    """Integrate reranker with QueryEngine."""
    # Create reranker
    reranker = CohereReranker(
        api_key="your-api-key",
        model="rerank-multilingual-v3.0"
    )

    # Initialize query engine with reranker
    # (Assuming you have other components initialized)
    # engine = QueryEngine(
    #     llm=llm,
    #     embedding_func=embedding_func,
    #     kv_storage=kv_storage,
    #     vector_storage=vector_storage,
    #     graph_storage=graph_storage,
    #     reranker=reranker  # ← Pass reranker here
    # )

    # Mix mode enables reranker by default
    param = QueryParam(
        query="What is machine learning?",
        mode=QueryMode.MIX,  # Reranker automatically applied
    )

    # result = await engine.query(param)

    print("\nQueryEngine configured with reranker")
    print("Mix mode will automatically apply reranking")


# ── Example 7: Multiple Reranker Types ───────────────────────────


async def example_multiple_rerankers():
    """Compare different reranker implementations."""
    query = "What is machine learning?"
    documents = [
        "Machine learning is AI subset.",
        "Python programming language.",
        "Deep learning neural networks.",
    ]

    rerankers = {
        "Cohere": CohereReranker(api_key="cohere-key"),
        "Jina": JinaReranker(api_key="jina-key"),
        "Aliyun": AliyunReranker(api_key="dashscope-key"),
        "vLLM": VLLMReranker(api_key=""),
    }

    print("\nComparing reranker types:")
    for name, reranker in rerankers.items():
        print(f"  - {name}: {type(reranker).__name__}")


# ── Example 8: Environment Variable Configuration ────────────────


async def example_env_config():
    """Load configuration from environment variables."""
    import os

    # Set environment variables
    os.environ["RERANKER_TYPE"] = "cohere"
    os.environ["RERANKER_API_KEY"] = "your-api-key"
    os.environ["RERANKER_TOP_K"] = "10"

    # Load from environment
    config = RerankerConfig.from_env()

    print(f"\nLoaded from environment:")
    print(f"  Type: {config.type}")
    print(f"  Top K: {config.top_k}")

    # Clean up
    del os.environ["RERANKER_TYPE"]
    del os.environ["RERANKER_API_KEY"]
    del os.environ["RERANKER_TOP_K"]


# ── Example 9: Min Score Filtering ───────────────────────────────


async def example_min_score():
    """Filter results by minimum score threshold."""
    reranker = CohereReranker(api_key="your-api-key")

    query = "What is machine learning?"
    documents = [
        "Machine learning is AI subset.",
        "Cooking recipes for pasta.",  # Low relevance
        "Deep learning neural networks.",
    ]

    # Only return results with score >= 0.5
    results = await reranker.rerank(
        query=query,
        documents=documents,
        top_n=10,
        min_score=0.5
    )

    print(f"\nFiltered by min_score=0.5: {len(results)} results")
    for result in results:
        print(f"  Score: {result.score:.3f}")


# ── Main ─────────────────────────────────────────────────────────


async def main():
    """Run all examples."""
    print("=" * 70)
    print("Aurora Reranker Examples")
    print("=" * 70)

    examples = [
        ("Basic Cohere Reranker", example_basic_cohere),
        ("Configuration-Based Setup", example_config_based),
        ("Robust Reranker", example_robust_reranker),
        ("Document Chunking", example_chunking),
        ("vLLM Self-Hosted", example_vllm),
        ("QueryEngine Integration", example_query_engine_integration),
        ("Multiple Reranker Types", example_multiple_rerankers),
        ("Environment Variables", example_env_config),
        ("Min Score Filtering", example_min_score),
    ]

    for name, example_func in examples:
        print(f"\n{'─' * 70}")
        print(f"Example: {name}")
        print(f"{'─' * 70}")

        try:
            await example_func()
        except Exception as e:
            print(f"\n⚠️  Example failed (expected without real API keys): {e}")

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

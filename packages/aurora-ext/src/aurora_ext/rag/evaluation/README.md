# RAGAS Evaluation Framework

This module provides RAG (Retrieval-Augmented Generation) quality evaluation using the [RAGAS](https://github.com/explodinggradients/ragas) framework.

## Overview

The RAGAS evaluation framework enables you to measure the quality of your RAG pipeline by computing four core metrics:

1. **Faithfulness** - Is the answer grounded in the retrieved context?
2. **Answer Relevancy** - Does the answer address the question?
3. **Context Precision** - Is the retrieved context relevant?
4. **Context Recall** - Does the context cover the ground truth?

## Installation

Install the RAGAS dependencies:

```bash
pip install 'aurora-ext[ragas]'
```

This will install:
- `ragas>=0.1.0,<0.3` - RAGAS evaluation framework
- `datasets>=2.14` - Hugging Face datasets
- `langchain-core>=0.1` - LangChain interfaces

## Quick Start

### Using the API

#### Evaluate a Knowledge Base

```bash
POST /api/v1/knowledge/{kb_name}/evaluate/
Content-Type: application/json

{
    "items": [
        {
            "query": "What is the capital of France?",
            "answer": "The capital of France is Paris.",
            "contexts": ["Paris is the capital and largest city of France."],
            "ground_truth": "Paris"
        }
    ],
    "metrics": ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
}
```

**Response:**

```json
{
    "scores": {
        "faithfulness": 0.95,
        "answer_relevancy": 0.88,
        "context_precision": 0.92,
        "context_recall": 0.85
    },
    "per_item_scores": [
        {
            "index": 0,
            "query": "What is the capital of France?",
            "scores": {
                "faithfulness": 0.95,
                "answer_relevancy": 0.88,
                "context_precision": 0.92,
                "context_recall": 0.85
            }
        }
    ],
    "num_items": 1,
    "metrics_requested": ["faithfulness", "answer_relevancy", "context_precision", "context_recall"],
    "elapsed_seconds": 2.345,
    "errors": []
}
```

#### Auto-Retrieve Contexts

If you don't have contexts yet, the API can automatically retrieve them from your knowledge base:

```bash
POST /api/v1/knowledge/{kb_name}/evaluate/
Content-Type: application/json

{
    "items": [
        {
            "query": "What is the capital of France?",
            "answer": "",
            "contexts": [],
            "ground_truth": "Paris"
        }
    ],
    "auto_retrieve": true,
    "query_mode": "mix"
}
```

#### Generate HTML Report

```bash
POST /api/v1/knowledge/{kb_name}/evaluate/html
Content-Type: application/json

{
    "items": [
        {
            "query": "What is the capital of France?",
            "answer": "The capital of France is Paris.",
            "contexts": ["Paris is the capital of France."],
            "ground_truth": "Paris"
        }
    ]
}
```

Returns an HTML report with formatted tables and error details.

### Using Python SDK

```python
from aurora_ext.rag.evaluation import (
    EvaluationItem,
    RAGASEvaluator,
    wrap_llm,
    wrap_embeddings,
)

# Create evaluation items
items = [
    EvaluationItem(
        query="What is the capital of France?",
        answer="The capital of France is Paris.",
        contexts=["Paris is the capital and largest city of France."],
        ground_truth="Paris",
    ),
]

# Initialize evaluator with LLM and embeddings (optional)
evaluator = RAGASEvaluator(
    llm=wrap_llm(your_aurora_llm),
    embeddings=wrap_embeddings(your_aurora_embeddings),
)

# Run evaluation
report = evaluator.evaluate(items)

# Access results
print(f"Faithfulness: {report.scores['faithfulness']:.2f}")
print(f"Answer Relevancy: {report.scores['answer_relevancy']:.2f}")

# Generate HTML report
html = report.to_html()
with open("evaluation_report.html", "w") as f:
    f.write(html)
```

## Metrics Explained

### Faithfulness (0.0 - 1.0)

Measures whether the answer is grounded in the retrieved context. A high score indicates the answer doesn't hallucinate information beyond what's in the context.

**Example:**
- Query: "What is the capital of France?"
- Context: "Paris is the capital of France."
- Answer (High Faithfulness): "The capital is Paris."
- Answer (Low Faithfulness): "The capital is Paris, which has a population of 2.1 million." (population not in context)

### Answer Relevancy (0.0 - 1.0)

Measures whether the answer addresses the question asked. A high score indicates the answer is relevant and directly answers the query.

**Example:**
- Query: "What is the capital of France?"
- Answer (High Relevancy): "The capital of France is Paris."
- Answer (Low Relevancy): "France is a country in Europe with many beautiful cities."

### Context Precision (0.0 - 1.0)

Measures whether the retrieved context is relevant to the question. A high score indicates the context contains information needed to answer the query.

**Example:**
- Query: "What is the capital of France?"
- Context (High Precision): "Paris is the capital and largest city of France."
- Context (Low Precision): "France is known for its cuisine and wine."

### Context Recall (0.0 - 1.0)

Measures whether the retrieved context covers the ground truth answer. Requires `ground_truth` to be provided. A high score indicates the context contains information about the correct answer.

**Example:**
- Query: "What is the capital of France?"
- Ground Truth: "Paris"
- Context (High Recall): "Paris is the capital of France."
- Context (Low Recall): "France is a European country."

**Note:** This metric is automatically skipped when `ground_truth` is not provided.

## Advanced Usage

### Selective Metrics

You can choose which metrics to compute:

```python
report = evaluator.evaluate(
    items,
    metrics=["faithfulness", "answer_relevancy"],
)
```

### Working with Datasets

Store and manage evaluation datasets:

```bash
# Create a dataset
POST /api/v1/evaluation/datasets
{
    "name": "my-evaluation-dataset",
    "description": "Test questions for knowledge base",
    "data": [
        {
            "query": "What is AI?",
            "answer": "AI is artificial intelligence.",
            "contexts": ["AI stands for artificial intelligence."],
            "ground_truth": "Artificial Intelligence"
        }
    ]
}

# List all datasets
GET /api/v1/evaluation/datasets

# Get specific dataset
GET /api/v1/evaluation/datasets/{id}

# Update dataset
PUT /api/v1/evaluation/datasets/{id}

# Delete dataset
DELETE /api/v1/evaluation/datasets/{id}
```

### Tracking Evaluation Tasks

Track evaluation runs and compare results:

```bash
# Create an evaluation task
POST /api/v1/evaluation/tasks
{
    "name": "evaluation-run-1",
    "model": "gpt-4",
    "dataset_id": "dataset-123",
    "status": "pending"
}

# Update task with results
PUT /api/v1/evaluation/tasks/{id}
{
    "status": "completed",
    "result": {
        "scores": {"faithfulness": 0.95},
        "elapsed_seconds": 2.5
    }
}

# List all tasks (history)
GET /api/v1/evaluation/tasks

# Get specific task
GET /api/v1/evaluation/tasks/{id}
```

## Comparing Configurations

Use evaluation tasks to compare different RAG configurations:

```python
# Configuration 1: chunk_size=500
result1 = evaluate_with_config(chunk_size=500)
create_task("config-1-chunk-500", result1)

# Configuration 2: chunk_size=1000
result2 = evaluate_with_config(chunk_size=1000)
create_task("config-2-chunk-1000", result2)

# Compare results
tasks = list_tasks()
for task in tasks:
    print(f"{task['name']}: {task['result']['scores']}")
```

## Error Handling

The evaluator handles errors gracefully:

- **Missing RAGAS**: Returns clear error message with installation instructions
- **RAGAS Errors**: Captures errors and includes them in the report
- **Missing Ground Truth**: Auto-skips context_recall metric
- **Empty Items**: Raises ValueError with helpful message

Example error response:

```json
{
    "scores": {},
    "per_item_scores": [],
    "num_items": 2,
    "metrics_requested": ["faithfulness"],
    "elapsed_seconds": 0.123,
    "errors": [
        "Skipped metrics requiring ground_truth: context_recall",
        "RAGAS evaluation error: Connection timeout"
    ]
}
```

## Best Practices

1. **Provide Ground Truth**: Include `ground_truth` when possible to enable context_recall
2. **Use Multiple Items**: Evaluate with at least 10-20 items for reliable aggregate scores
3. **Track Over Time**: Store evaluation results to track improvements
4. **Compare Configurations**: Use evaluation to compare different chunk sizes, retrieval strategies, etc.
5. **Auto-Retrieve**: Use `auto_retrieve=true` for quick evaluations without pre-computed contexts

## Testing

Run the test suite:

```bash
# Run all evaluation tests
pytest tests/ext/test_ragas_evaluator.py tests/ext/test_langchain_adapter.py -v

# Run with coverage
python -m coverage run --source=packages/aurora-ext/src/aurora_ext/rag/evaluation \
    -m pytest tests/ext/test_ragas_evaluator.py tests/ext/test_langchain_adapter.py
python -m coverage report --show-missing
```

Current coverage: **89%** (30 tests)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                               │
│  POST /api/v1/knowledge/{kb}/evaluate/                      │
│  POST /api/v1/knowledge/{kb}/evaluate/html                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                 Service Layer                                │
│  KnowledgeV2Service.evaluate()                              │
│  - Auto-retrieve contexts                                   │
│  - Wrap Aurora LLM/Embeddings                               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Evaluation Layer                                │
│  RAGASEvaluator                                             │
│  - Build RAGAS dataset                                      │
│  - Build RAGAS metrics                                      │
│  - Run evaluation                                           │
│  - Extract scores                                           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Adapter Layer                                   │
│  wrap_llm() - Aurora LLM → LangChain BaseChatModel         │
│  wrap_embeddings() - Aurora Embeddings → LangChain Embed   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  RAGAS Framework                             │
│  - faithfulness metric                                      │
│  - answer_relevancy metric                                  │
│  - context_precision metric                                 │
│  - context_recall metric                                    │
└─────────────────────────────────────────────────────────────┘
```

## References

- [RAGAS Documentation](https://docs.ragas.io/)
- [RAGAS GitHub](https://github.com/explodinggradients/ragas)
- [RAGAS Paper](https://arxiv.org/abs/2309.15217)
- [LangChain Documentation](https://python.langchain.com/)

## Support

For issues or questions:
1. Check the test suite for usage examples
2. Review the API documentation at `/docs` (FastAPI auto-generated)
3. Consult the RAGAS documentation for metric-specific questions

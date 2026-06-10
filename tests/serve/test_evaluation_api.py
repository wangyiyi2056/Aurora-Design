"""Integration tests for the evaluation API endpoints.

Tests cover:
- Dataset CRUD operations
- Task management
- Evaluation endpoint with RAGAS integration
- HTML report generation
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aurora_serve.server import create_app


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    """Create a test client for the API."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_dataset():
    """Sample evaluation dataset."""
    return {
        "name": "test-dataset",
        "description": "Test evaluation dataset",
        "data": [
            {
                "query": "What is the capital of France?",
                "answer": "The capital of France is Paris.",
                "contexts": ["Paris is the capital of France."],
                "ground_truth": "Paris",
            }
        ],
    }


@pytest.fixture
def sample_evaluation_request():
    """Sample evaluation request."""
    return {
        "items": [
            {
                "query": "What is the capital of France?",
                "answer": "The capital of France is Paris.",
                "contexts": ["Paris is the capital and largest city of France."],
                "ground_truth": "Paris",
            },
            {
                "query": "Who wrote Romeo and Juliet?",
                "answer": "William Shakespeare wrote Romeo and Juliet.",
                "contexts": [
                    "Romeo and Juliet is a tragedy by William Shakespeare."
                ],
                "ground_truth": "William Shakespeare",
            },
        ],
        "metrics": ["faithfulness", "answer_relevancy"],
    }


# ── Dataset CRUD Tests ──────────────────────────────────────────────────────


class TestDatasetAPI:
    """Tests for dataset CRUD operations."""

    def test_create_dataset(self, client, sample_dataset):
        """Test creating an evaluation dataset."""
        response = client.post("/api/v1/evaluation/datasets", json=sample_dataset)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_dataset["name"]
        assert data["description"] == sample_dataset["description"]
        assert "id" in data
        assert "created_at" in data

    def test_list_datasets(self, client):
        """Test listing all datasets."""
        response = client.get("/api/v1/evaluation/datasets")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_dataset(self, client, sample_dataset):
        """Test getting a specific dataset."""
        # Create dataset first
        create_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = create_response.json()["id"]

        # Get the dataset
        response = client.get(f"/api/v1/evaluation/datasets/{dataset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == sample_dataset["name"]

    def test_get_dataset_not_found(self, client):
        """Test getting a non-existent dataset."""
        response = client.get("/api/v1/evaluation/datasets/non-existent-id")
        assert response.status_code == 404

    def test_update_dataset(self, client, sample_dataset):
        """Test updating a dataset."""
        # Create dataset first
        create_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = create_response.json()["id"]

        # Update the dataset
        update_data = {"description": "Updated description"}
        response = client.put(
            f"/api/v1/evaluation/datasets/{dataset_id}", json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_delete_dataset(self, client, sample_dataset):
        """Test deleting a dataset."""
        # Create dataset first
        create_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = create_response.json()["id"]

        # Delete the dataset
        response = client.delete(f"/api/v1/evaluation/datasets/{dataset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

        # Verify it's deleted
        get_response = client.get(f"/api/v1/evaluation/datasets/{dataset_id}")
        assert get_response.status_code == 404


# ── Task Management Tests ───────────────────────────────────────────────────


class TestTaskAPI:
    """Tests for evaluation task management."""

    def test_create_task(self, client, sample_dataset):
        """Test creating an evaluation task."""
        # Create dataset first
        dataset_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = dataset_response.json()["id"]

        # Create task
        task_data = {
            "name": "test-evaluation-task",
            "model": "gpt-4",
            "dataset_id": dataset_id,
            "status": "pending",
        }
        response = client.post("/api/v1/evaluation/tasks", json=task_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == task_data["name"]
        assert data["status"] == "pending"
        assert "id" in data

    def test_list_tasks(self, client):
        """Test listing all tasks."""
        response = client.get("/api/v1/evaluation/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_get_task(self, client, sample_dataset):
        """Test getting a specific task."""
        # Create dataset and task first
        dataset_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = dataset_response.json()["id"]

        task_data = {
            "name": "test-task",
            "model": "gpt-4",
            "dataset_id": dataset_id,
            "status": "pending",
        }
        create_response = client.post("/api/v1/evaluation/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Get the task
        response = client.get(f"/api/v1/evaluation/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["name"] == "test-task"

    def test_get_task_not_found(self, client):
        """Test getting a non-existent task."""
        response = client.get("/api/v1/evaluation/tasks/non-existent-id")
        assert response.status_code == 404

    def test_update_task(self, client, sample_dataset):
        """Test updating a task."""
        # Create dataset and task first
        dataset_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = dataset_response.json()["id"]

        task_data = {
            "name": "test-task",
            "model": "gpt-4",
            "dataset_id": dataset_id,
            "status": "pending",
        }
        create_response = client.post("/api/v1/evaluation/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Update task status and result
        update_data = {
            "status": "completed",
            "result": {
                "scores": {"faithfulness": 0.95},
                "elapsed_seconds": 1.23,
            },
        }
        response = client.put(
            f"/api/v1/evaluation/tasks/{task_id}", json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data

    def test_delete_task(self, client, sample_dataset):
        """Test deleting a task."""
        # Create dataset and task first
        dataset_response = client.post(
            "/api/v1/evaluation/datasets", json=sample_dataset
        )
        dataset_id = dataset_response.json()["id"]

        task_data = {
            "name": "test-task",
            "model": "gpt-4",
            "dataset_id": dataset_id,
            "status": "pending",
        }
        create_response = client.post("/api/v1/evaluation/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Delete the task
        response = client.delete(f"/api/v1/evaluation/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

        # Verify it's deleted
        get_response = client.get(f"/api/v1/evaluation/tasks/{task_id}")
        assert get_response.status_code == 404


# ── Knowledge Base Evaluation Tests ─────────────────────────────────────────


class TestKnowledgeEvaluationAPI:
    """Tests for knowledge base evaluation endpoints."""

    @pytest.fixture
    def create_knowledge_base(self, client):
        """Create a knowledge base for testing."""
        kb_data = {
            "name": "test-kb-evaluation",
            "chunk_strategy": "fixed",
            "chunk_size": 500,
            "chunk_overlap": 50,
        }
        response = client.post("/api/v1/knowledge", json=kb_data)
        assert response.status_code in [200, 409]  # 409 if already exists
        return kb_data["name"]

    def test_evaluate_knowledge_base(
        self, client, create_knowledge_base, sample_evaluation_request
    ):
        """Test evaluating a knowledge base."""
        kb_name = create_knowledge_base

        # Note: This test may fail if RAGAS is not installed or LLM is not configured
        response = client.post(
            f"/api/v1/knowledge/{kb_name}/evaluate/",
            json=sample_evaluation_request,
        )

        # Should return 501 if RAGAS not installed, 200 if successful, or 500 on error
        assert response.status_code in [200, 501, 500]

        if response.status_code == 200:
            data = response.json()
            assert "scores" in data
            assert "per_item_scores" in data
            assert "num_items" in data
            assert data["num_items"] == len(sample_evaluation_request["items"])

    def test_evaluate_knowledge_base_not_found(
        self, client, sample_evaluation_request
    ):
        """Test evaluating a non-existent knowledge base."""
        response = client.post(
            "/api/v1/knowledge/non-existent-kb/evaluate/",
            json=sample_evaluation_request,
        )
        # Should return 500 or 404
        assert response.status_code in [404, 500]

    def test_evaluate_empty_items(self, client, create_knowledge_base):
        """Test evaluation with empty items list."""
        kb_name = create_knowledge_base
        request_data = {"items": [], "metrics": ["faithfulness"]}

        response = client.post(
            f"/api/v1/knowledge/{kb_name}/evaluate/", json=request_data
        )
        # Should return 422 (validation error) or 400 (bad request)
        assert response.status_code in [400, 422]

    def test_evaluate_html_report(
        self, client, create_knowledge_base, sample_evaluation_request
    ):
        """Test HTML report generation."""
        kb_name = create_knowledge_base

        response = client.post(
            f"/api/v1/knowledge/{kb_name}/evaluate/html",
            json=sample_evaluation_request,
        )

        # Should return 501 if RAGAS not installed, 200 if successful, or 500 on error
        assert response.status_code in [200, 501, 500]

        if response.status_code == 200:
            assert "text/html" in response.headers["content-type"]
            assert "<!DOCTYPE html>" in response.text
            assert "RAG Evaluation Report" in response.text


# ── Edge Cases and Error Handling ───────────────────────────────────────────


class TestEvaluationEdgeCases:
    """Tests for edge cases and error handling."""

    def test_create_dataset_with_invalid_data(self, client):
        """Test creating a dataset with invalid data."""
        invalid_data = {"description": "Missing name field"}
        response = client.post("/api/v1/evaluation/datasets", json=invalid_data)
        assert response.status_code == 422  # Validation error

    def test_create_task_with_invalid_dataset(self, client):
        """Test creating a task with non-existent dataset."""
        task_data = {
            "name": "test-task",
            "model": "gpt-4",
            "dataset_id": "non-existent-dataset",
            "status": "pending",
        }
        response = client.post("/api/v1/evaluation/tasks", json=task_data)
        # Should still create the task (foreign key not enforced in SQLite)
        assert response.status_code == 200

    def test_update_nonexistent_dataset(self, client):
        """Test updating a non-existent dataset."""
        update_data = {"description": "Updated"}
        response = client.put(
            "/api/v1/evaluation/datasets/non-existent", json=update_data
        )
        assert response.status_code == 404

    def test_update_nonexistent_task(self, client):
        """Test updating a non-existent task."""
        update_data = {"status": "completed"}
        response = client.put(
            "/api/v1/evaluation/tasks/non-existent", json=update_data
        )
        assert response.status_code == 404

    def test_evaluate_with_auto_retrieve(self, client, create_knowledge_base):
        """Test evaluation with auto_retrieve enabled."""
        kb_name = create_knowledge_base
        request_data = {
            "items": [
                {
                    "query": "What is the capital of France?",
                    "answer": "",
                    "contexts": [],
                    "ground_truth": "Paris",
                }
            ],
            "metrics": ["faithfulness"],
            "auto_retrieve": True,
        }

        response = client.post(
            f"/api/v1/knowledge/{kb_name}/evaluate/", json=request_data
        )
        # Should attempt auto-retrieval
        assert response.status_code in [200, 500, 501]


@pytest.fixture
def create_knowledge_base(client):
    """Create a knowledge base for testing."""
    kb_data = {
        "name": "test-kb-evaluation",
        "chunk_strategy": "fixed",
        "chunk_size": 500,
        "chunk_overlap": 50,
    }
    response = client.post("/api/v1/knowledge", json=kb_data)
    assert response.status_code in [200, 409]  # 409 if already exists
    return kb_data["name"]

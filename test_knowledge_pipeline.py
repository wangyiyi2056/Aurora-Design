#!/usr/bin/env python
"""
Test script to verify the knowledge pipeline works correctly.

This script:
1. Creates a test file
2. Uploads it via the API
3. Monitors pipeline status
4. Checks document processing status
"""

import asyncio
import httpx
import json
import tempfile
import time
from pathlib import Path


API_BASE = "http://localhost:8888/api/v1"
KB_NAME = "test-kb"


async def create_test_file() -> Path:
    """Create a test markdown file with unique content."""
    import random
    unique_id = random.randint(10000, 99999)

    content = f"""# Test Document {unique_id}

This is a unique test document for the knowledge pipeline (ID: {unique_id}).

## Section 1: Introduction

Knowledge graphs are powerful tools for organizing and querying information.
They represent entities and their relationships in a structured format.

## Section 2: Entities

Some example entities:
- **Albert Einstein {unique_id}**: Physicist who developed the theory of relativity
- **Theory of Relativity {unique_id}**: Fundamental theory in physics
- **Princeton University {unique_id}**: Where Einstein worked for many years

## Section 3: Relationships

The relationships between these entities are:
- Einstein {unique_id} *developed* Theory of Relativity {unique_id}
- Einstein {unique_id} *worked at* Princeton University {unique_id}
- Theory of Relativity {unique_id} *is studied at* Princeton University {unique_id}

This document contains enough information to test entity extraction,
relationship identification, and knowledge graph construction.

Unique identifier: {unique_id}-{time.time()}
"""
    test_file = Path(tempfile.gettempdir()) / f"test_knowledge_{unique_id}.md"
    test_file.write_text(content)
    print(f"✅ Created test file: {test_file} (ID: {unique_id})")
    return test_file


async def upload_file(client: httpx.AsyncClient, file_path: Path) -> dict:
    """Upload a file to the knowledge base."""
    print(f"\n📤 Uploading file: {file_path.name}")

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "text/markdown")}

        # V2 endpoint: /api/v1/knowledge/{name}/documents/upload
        response = await client.post(
            f"{API_BASE}/knowledge/{KB_NAME}/documents/upload",
            files=files,
        )

    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:500]}")

    if response.status_code != 200:
        print(f"❌ Upload failed with status {response.status_code}")
        return {"status": "error", "message": response.text}

    result = response.json()
    print(f"✅ Upload response: {json.dumps(result, indent=2)}")
    return result


async def monitor_pipeline(client: httpx.AsyncClient, max_wait: int = 120):
    """Monitor pipeline status until completion."""
    print(f"\n🔍 Monitoring pipeline status (max {max_wait}s)...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Get pipeline status (V2 endpoint)
        response = await client.get(f"{API_BASE}/knowledge/{KB_NAME}/documents/pipeline_status")

        if response.status_code != 200:
            print(f"  ❌ Failed to get pipeline status: {response.status_code}")
            await asyncio.sleep(2)
            continue

        status = response.json()

        busy = status.get("busy", False)
        docs = status.get("docs", {})
        pending = docs.get("pending", 0)
        processing = docs.get("processing", 0)
        completed = docs.get("processed", 0)
        failed = docs.get("failed", 0)

        print(
            f"  ⏱️  Pipeline: busy={busy}, "
            f"pending={pending}, processing={processing}, "
            f"completed={completed}, failed={failed}"
        )

        if not busy and pending == 0 and processing == 0:
            print("✅ Pipeline finished!")
            return status

        await asyncio.sleep(2)

    print("⚠️  Timeout waiting for pipeline")
    return None


async def check_documents(client: httpx.AsyncClient):
    """Check the status of all documents."""
    print("\n📄 Checking document status...")

    # V2 endpoint: POST /knowledge/{name}/documents/paginated
    response = await client.post(
        f"{API_BASE}/knowledge/{KB_NAME}/documents/paginated",
        json={"page": 1, "page_size": 100}
    )

    if response.status_code != 200:
        print(f"❌ Failed to list documents: {response.status_code}")
        return []

    result = response.json()
    documents = result.get("items", [])
    print(f"Total documents: {len(documents)}")

    for doc in documents:
        doc_id = doc.get("id", "unknown")
        status = doc.get("status", "unknown")
        error = doc.get("error", "")

        status_icon = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "failed": "❌",
        }.get(status, "❓")

        print(f"  {status_icon} {doc_id}: {status}")
        if error:
            print(f"      Error: {error}")

    return documents


async def main():
    """Main test flow."""
    print("=" * 60)
    print("Knowledge Pipeline Test")
    print("=" * 60)

    # Create test file
    test_file = await create_test_file()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Upload file
        upload_result = await upload_file(client, test_file)

        if upload_result.get("status") != "success":
            print(f"❌ Upload failed: {upload_result}")
            return

        # Monitor pipeline
        pipeline_status = await monitor_pipeline(client)

        # Check documents
        documents = await check_documents(client)

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        completed = sum(1 for d in documents if d.get("status") == "completed")
        failed = sum(1 for d in documents if d.get("status") == "failed")

        print(f"✅ Completed: {completed}")
        print(f"❌ Failed: {failed}")

        if completed > 0 and failed == 0:
            print("\n🎉 Test PASSED!")
        else:
            print("\n⚠️  Test FAILED - check logs for details")

    # Cleanup
    test_file.unlink(missing_ok=True)
    print(f"\n🧹 Cleaned up test file")


if __name__ == "__main__":
    asyncio.run(main())

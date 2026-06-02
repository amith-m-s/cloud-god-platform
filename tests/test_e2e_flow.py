"""End-to-end flow tests: register -> create doc -> seed -> search -> chat."""
from __future__ import annotations

import io
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_full_rag_flow(client: TestClient, auth_headers: dict):
    """Test the complete document -> search -> chat pipeline."""
    # 1. Create a document record via upload (mocked S3)
    with patch("app.services.document_service.upload_bytes_to_s3", return_value="test/doc.txt"):
        with patch("app.services.document_service.enqueue_document_job"):
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("knowledge.txt", io.BytesIO(b"test content"), "text/plain")},
                data={"tenant_id": "default"},
                headers=auth_headers,
            )
            assert resp.status_code == 201
            doc_id = resp.json()["id"]

    # 2. Seed the document with real text
    resp = client.post(
        "/api/v1/documents/seed",
        json={
            "document_id": doc_id,
            "tenant_id": "default",
            "text": (
                "FastAPI is a modern, fast web framework for building APIs with Python. "
                "It is based on standard Python type hints and uses Starlette for the web parts. "
                "FastAPI provides automatic interactive API documentation via Swagger UI and ReDoc. "
                "It supports dependency injection, OAuth2 with JWT tokens, and WebSocket connections. "
                "FastAPI is one of the fastest Python frameworks available, comparable to NodeJS and Go."
            ),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    seed_data = resp.json()
    assert seed_data["document_id"] == doc_id
    assert seed_data["chunks_created"] >= 1
    assert seed_data["status"] == "indexed"

    # 3. Verify document is now listed and indexed
    resp = client.get("/api/v1/documents?tenant_id=default", headers=auth_headers)
    assert resp.status_code == 200
    docs = resp.json()
    assert docs["pagination"]["total"] >= 1
    found = [d for d in docs["items"] if d["id"] == doc_id]
    assert len(found) == 1
    assert found[0]["status"] == "indexed"

    # 4. Search for content
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "FastAPI framework", "tenant_id": "default", "top_k": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    search_data = resp.json()
    assert len(search_data["results"]) >= 1
    assert search_data["results"][0]["score"] > 0

    # 5. Chat with the knowledge base
    resp = client.post(
        "/api/v1/chat",
        json={"question": "FastAPI Python framework features", "tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    chat_data = resp.json()
    assert len(chat_data["answer"]) > 0
    assert len(chat_data["sources"]) >= 1


def test_search_no_results(client: TestClient, auth_headers: dict):
    """Search with no indexed documents returns empty results."""
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "nonexistent content", "tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_chat_no_context(client: TestClient, auth_headers: dict):
    """Chat with no documents returns a helpful fallback message."""
    resp = client.post(
        "/api/v1/chat",
        json={"question": "What is the meaning of life?", "tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "could not find" in data["answer"].lower() or len(data["answer"]) > 0
    assert data["sources"] == []


def test_chat_stream_no_context(client: TestClient, auth_headers: dict):
    """Chat stream with no documents returns a helpful fallback stream."""
    resp = client.post(
        "/api/v1/chat/stream",
        json={"question": "What is the meaning of life?", "tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    lines = [line if isinstance(line, str) else line.decode("utf-8") for line in resp.iter_lines() if line.strip()]
    assert any("System Notification" in line for line in lines)
    assert any("sources" in line for line in lines)
    assert any("done" in line for line in lines)


def test_chat_stream_flow(client: TestClient, auth_headers: dict):
    """Test full flow and verify streaming output."""
    # 1. Create a document record via upload (mocked S3)
    with patch("app.services.document_service.upload_bytes_to_s3", return_value="test/doc.txt"):
        with patch("app.services.document_service.enqueue_document_job"):
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("knowledge.txt", io.BytesIO(b"test content"), "text/plain")},
                data={"tenant_id": "default"},
                headers=auth_headers,
            )
            assert resp.status_code == 201
            doc_id = resp.json()["id"]

    # 2. Seed the document with real text
    resp = client.post(
        "/api/v1/documents/seed",
        json={
            "document_id": doc_id,
            "tenant_id": "default",
            "text": "FastAPI is a modern, fast web framework for building APIs with Python.",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 3. Stream chat response
    resp = client.post(
        "/api/v1/chat/stream",
        json={"question": "FastAPI features", "tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    lines = [line if isinstance(line, str) else line.decode("utf-8") for line in resp.iter_lines() if line.strip()]
    assert any("sources" in line for line in lines)
    assert any("FastAPI" in line or "Insight" in line or "Context segment" in line or "Dynamic Context Synthesizer" in line for line in lines)
    assert any("done" in line for line in lines)



def test_register_and_full_auth_cycle(client: TestClient):
    """Test the complete auth lifecycle: register -> login -> me -> refresh -> me again."""
    # Register
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "lifecycle@test.com", "password": "strongpass123", "full_name": "Lifecycle User"},
    )
    assert resp.status_code == 201
    tokens = resp.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Me with access token
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200
    user = resp.json()
    assert user["email"] == "lifecycle@test.com"
    assert user["full_name"] == "Lifecycle User"
    assert user["role"] == "user"
    assert user["is_active"] is True

    # Login with same credentials
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "lifecycle@test.com", "password": "strongpass123"},
    )
    assert resp.status_code == 200

    # Refresh
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    assert len(new_access) > 0  # got a valid token back

    # Me with refreshed token still works
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "lifecycle@test.com"


def test_request_id_header(client: TestClient):
    """Every response must include X-Request-ID header."""
    resp = client.get("/health")
    assert "x-request-id" in resp.headers
    rid = resp.headers["x-request-id"]
    assert len(rid) == 36  # UUID v4 format
    assert rid.count("-") == 4


def test_validation_error_details(client: TestClient, auth_headers: dict):
    """422 responses should include detailed validation errors."""
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "", "tenant_id": "default"},  # empty query violates min_length=1
        headers=auth_headers,
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "errors" in data
    assert len(data["errors"]) > 0

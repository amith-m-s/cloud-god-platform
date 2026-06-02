from __future__ import annotations

import io
from unittest.mock import patch


def test_upload_requires_auth(client):
    resp = client.post("/api/v1/documents/upload", files={"file": ("test.txt", b"hello")})
    assert resp.status_code == 401


@patch("app.services.document_service.upload_bytes_to_s3", return_value="key")
@patch("app.services.document_service.enqueue_document_job")
def test_upload_document(mock_queue, mock_s3, client, auth_headers):
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        data={"tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.txt"
    assert data["status"] == "queued"


def test_list_documents_empty(client, auth_headers):
    resp = client.get("/api/v1/documents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0


def test_list_documents_requires_auth(client):
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 401


def test_search_requires_auth(client):
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "test"},
    )
    assert resp.status_code == 401


def test_delete_requires_auth(client):
    resp = client.delete("/api/v1/documents/1")
    assert resp.status_code == 401


@patch("app.services.s3_service.delete_from_s3")
@patch("app.services.document_service.upload_bytes_to_s3", return_value="key")
@patch("app.services.document_service.enqueue_document_job")
def test_delete_document_success(mock_queue, mock_s3, mock_delete, client, auth_headers):
    # Upload first
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        data={"tenant_id": "default"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # Delete
    resp = client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify document is gone
    resp = client.get("/api/v1/documents", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 0

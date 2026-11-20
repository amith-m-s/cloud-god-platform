from __future__ import annotations

from uuid import UUID

import pytest


def test_request_id_preserves_safe_client_value(client):
    request_id = "trace_2026-11-20.01"
    response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.parametrize("request_id", ["trace id", "x" * 65, ""])
def test_request_id_replaces_unsafe_or_unbounded_client_values(client, request_id):
    response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    generated_id = response.headers["X-Request-ID"]
    assert generated_id != request_id
    assert str(UUID(generated_id)) == generated_id


def test_request_id_is_generated_when_header_is_missing(client):
    response = client.get("/health")

    assert response.status_code == 200
    generated_id = response.headers["X-Request-ID"]
    assert str(UUID(generated_id)) == generated_id

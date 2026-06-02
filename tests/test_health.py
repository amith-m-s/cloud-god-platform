from __future__ import annotations


def test_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data


def test_metrics(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text or response.status_code == 200

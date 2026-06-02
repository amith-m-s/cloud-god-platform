from __future__ import annotations


def test_register_success(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123", "full_name": "New User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_short_password(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "123"},
    )
    assert resp.status_code == 422


def test_login_success(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrong@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )
    assert resp.status_code == 401


def test_refresh_token(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@example.com", "password": "password123"},
    )
    refresh_token = reg.json()["refresh_token"]
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_me_endpoint(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"


def test_me_unauthenticated(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401

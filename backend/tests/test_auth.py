"""TDD: Auth endpoint tests — login, logout, JWT verification."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_happy_path():
    """Seed admin user can login and receive JWT token."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@arukai.example", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_wrong_password():
    """Wrong password returns 401."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@arukai.example", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_unknown_email():
    """Unknown email returns 401."""
    response = client.post(
        "/auth/login",
        json={"email": "nobody@nowhere.example", "password": "anything"},
    )
    assert response.status_code == 401


def test_login_reviewer():
    """Seed reviewer user can also login."""
    response = client.post(
        "/auth/login",
        json={"email": "reviewer@arukai.example", "password": "reviewer123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_jwt_verification_via_me():
    """Valid JWT allows access to /auth/me endpoint."""
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@arukai.example", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    user = me_resp.json()
    assert user["email"] == "admin@arukai.example"
    assert user["role"] == "admin"
    assert "id" in user


def test_me_without_token():
    """No token → 401."""
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_invalid_token():
    """Garbage token → 401."""
    response = client.get("/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert response.status_code == 401


def test_logout():
    """Logout invalidates the session — subsequent /auth/me with same token returns 401."""
    login_resp = client.post(
        "/auth/login",
        json={"email": "reviewer@arukai.example", "password": "reviewer123"},
    )
    token = login_resp.json()["access_token"]

    logout_resp = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_resp.status_code == 200

    # After logout, same token should fail
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 401

"""Tests for authentication endpoints (login, token validation, user profile)."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import get_auth_header


def test_login_success(client: TestClient, seeded_db: dict) -> None:
    """Verify valid credentials return a valid JWT bearer token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_invalid_password_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify wrong password returns HTTP 401 and generic error."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "IncorrectPassword!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_unknown_user_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify non-existent email returns HTTP 401 and generic error."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_inactive_user_rejected(client: TestClient, seeded_db: dict) -> None:
    """Verify inactive user account is rejected at login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 401
    assert "Account is deactivated" in response.json()["detail"]


def test_get_me_unauthenticated_rejected(client: TestClient) -> None:
    """Verify /api/v1/auth/me returns HTTP 401 when Authorization header is missing."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


def test_get_me_invalid_token_rejected(client: TestClient) -> None:
    """Verify invalid or forged token returns HTTP 401."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer forged-or-invalid-token"},
    )
    assert response.status_code == 401
    assert "Invalid or expired authentication token" in response.json()["detail"]


def test_get_me_authenticated_success(client: TestClient, seeded_db: dict) -> None:
    """Verify authenticated user can fetch their verified server-side profile."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]

    headers = get_auth_header(alice.id)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["department"]["name"] == "Engineering"
    assert len(data["roles"]) == 1
    assert data["roles"][0]["name"] == "employee"
    assert data["is_active"] is True

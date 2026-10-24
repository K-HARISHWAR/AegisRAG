"""Tests for health check endpoints, request ID propagation, and error sanitization."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_root_endpoint(client: TestClient) -> None:
    """Verify root endpoint returns project identity and request ID header."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "AegisRAG" in data["name"]
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


def test_liveness_endpoint(client: TestClient) -> None:
    """Verify /health/live returns HTTP 200 and live status."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "live"
    assert "timestamp" in data
    assert "X-Request-ID" in response.headers


def test_readiness_endpoint(client: TestClient) -> None:
    """Verify /health/ready returns HTTP 200, ready status, and dependency checks."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["configuration"] == "healthy"
    assert data["checks"]["storage"] == "healthy"


def test_readiness_no_credential_or_path_leakage(client: TestClient) -> None:
    """Verify /health/ready response never exposes passwords, secrets, DB URLs, or absolute paths."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    raw_content = response.text.lower()

    # Must NOT expose credentials, database connection strings, or system paths
    forbidden_terms = [
        "postgres",
        "secret",
        "password",
        "database_url",
        "://",
        "c:\\",
        "uploads",
        "backend/data",
    ]
    for term in forbidden_terms:
        assert term not in raw_content, f"Leaked sensitive term '{term}' in health response"


def test_request_id_middleware_preserves_incoming_header(client: TestClient) -> None:
    """Verify client-supplied X-Request-ID is preserved in response."""
    custom_id = "client-req-9876543210"
    response = client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


def test_request_id_middleware_generates_uuid_when_omitted(client: TestClient) -> None:
    """Verify server generates a non-empty request ID when omitted by client."""
    response = client.get("/health/live")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) >= 16


def test_unhandled_exception_sanitization(test_settings: Settings) -> None:
    """Verify unhandled exceptions return HTTP 500 with a generic message and no stack traces."""
    app = create_app(test_settings)

    # Add a route that deliberately raises an unexpected internal exception
    @app.get("/test-internal-error")
    async def trigger_error():
        raise RuntimeError("Internal critical error with sensitive file path: /etc/secrets/key.pem")

    error_client = TestClient(app, raise_server_exceptions=False)
    response = error_client.get("/test-internal-error")

    assert response.status_code == 500
    data = response.json()

    # Response must contain generic detail and request ID
    assert "An internal server error occurred" in data["detail"]
    assert "request_id" in data

    # Response must NOT expose the internal exception message or sensitive file path
    assert "RuntimeError" not in response.text
    assert "key.pem" not in response.text
    assert "secrets" not in response.text

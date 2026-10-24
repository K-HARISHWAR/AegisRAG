"""Pytest fixtures for backend tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Fixture returning settings configured for test environment."""
    return Settings(
        ENVIRONMENT="test",
        DEBUG=True,
        SECRET_KEY="test-secret-key-for-unit-testing-at-least-32-chars-long",
        LOG_LEVEL="DEBUG",
        LOCAL_STORAGE_DIR="backend/data/test_uploads",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Fixture returning synchronous FastAPI TestClient."""
    app = create_app(test_settings)
    return TestClient(app)

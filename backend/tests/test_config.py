"""Tests for typed configuration and fail-closed validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings_load() -> None:
    """Verify that default development settings load successfully."""
    settings = Settings()
    assert settings.PROJECT_NAME == "AegisRAG Enterprise Assistant"
    assert settings.ENVIRONMENT in ["development", "test"]
    assert settings.BACKEND_PORT == 8000
    assert "pdf" in settings.ALLOWED_EXTENSIONS


def test_log_level_validation() -> None:
    """Verify that log level validator accepts valid levels and rejects invalid ones."""
    valid_settings = Settings(LOG_LEVEL="debug")
    assert valid_settings.LOG_LEVEL == "DEBUG"

    with pytest.raises(ValidationError) as exc_info:
        Settings(LOG_LEVEL="INVALID_LEVEL")
    assert "LOG_LEVEL must be one of" in str(exc_info.value)


def test_production_debug_fail_closed() -> None:
    """Verify that production environment fails fast if DEBUG is True."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            SECRET_KEY="a-very-secure-random-token-that-is-over-32-characters-long!",
        )
    assert "DEBUG must be False in production" in str(exc_info.value)


def test_production_weak_secret_key_fail_closed() -> None:
    """Verify that production environment fails fast if SECRET_KEY contains insecure strings or is too short."""
    # Test short key
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY="short-key",
        )
    assert "SECRET_KEY must be a secure random string" in str(exc_info.value)

    # Test dev/secret in key
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY="dev-insecure-key-that-is-long-enough-32-chars-long",
        )
    assert "SECRET_KEY must be a secure random string" in str(exc_info.value)


def test_production_valid_settings() -> None:
    """Verify that production environment succeeds when valid settings are provided."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY="k8!mQ#91pZ$vL2wE5yR8tU4oI7aS0dF3gH6jK",
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False

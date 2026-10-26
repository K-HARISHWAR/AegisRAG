"""Tests for password hashing and JWT token cryptographic security."""

import time
import uuid
from datetime import timedelta
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    """Verify bcrypt hashes passwords uniquely with salt and verifies correctly."""
    plain = "SuperSecurePassword123!"
    hashed1 = hash_password(plain)
    hashed2 = hash_password(plain)

    # Salt ensures identical passwords produce different hashes
    assert hashed1 != hashed2
    assert hashed1.startswith("$2b$") or hashed1.startswith("$2a$")

    # Verification
    assert verify_password(plain, hashed1) is True
    assert verify_password(plain, hashed2) is True
    assert verify_password("WrongPassword!", hashed1) is False


def test_jwt_create_and_decode_valid_token() -> None:
    """Verify JWT access token encodes subject and decodes correctly."""
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload.sub == str(user_id)
    assert payload.type == "access"
    assert payload.exp > time.time()


def test_jwt_expired_token_fails_closed() -> None:
    """Verify expired JWT tokens are rejected and return None."""
    user_id = uuid.uuid4()
    # Expired 5 seconds ago
    expired_token = create_access_token(user_id, expires_delta=timedelta(seconds=-5))
    payload = decode_access_token(expired_token)
    assert payload is None


def test_jwt_tampered_token_fails_closed() -> None:
    """Verify modifying any character in the token invalidates cryptographic signature."""
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    # Tamper with the last character of the signature
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    payload = decode_access_token(tampered)
    assert payload is None


def test_jwt_malformed_string_fails_closed() -> None:
    """Verify arbitrary random strings are rejected safely without exceptions."""
    assert decode_access_token("not-a-real-token") is None
    assert decode_access_token("") is None

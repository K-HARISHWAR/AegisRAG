"""Cryptographic utilities: bcrypt password hashing and PyJWT token management."""

import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

from app.core.config import get_settings
from app.schemas.auth import TokenPayload

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with a randomized salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash in constant time."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str | uuid.UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token for an authenticated subject."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token


def decode_access_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT access token. Fail closed on any invalidity."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        if payload.get("type") != "access":
            return None
        return TokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            type=payload["type"],
        )
    except jwt.PyJWTError:
        return None
    except Exception:
        return None

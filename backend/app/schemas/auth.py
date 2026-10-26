"""Authentication and token Pydantic schemas."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """User login credentials payload."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """Bearer access token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded JWT claims payload."""

    sub: str
    exp: int
    type: str = "access"

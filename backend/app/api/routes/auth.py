"""Authentication routes for login and user profile inspection."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserRead
from app.services.audit import log_audit_event

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="User login",
    description="Authenticate with email and password to receive a JWT access token.",
)
async def login(
    request: Request,
    credentials: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate credentials and issue JWT bearer token."""
    stmt = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.department))
        .where(User.email == credentials.email.lower().strip())
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    ip_address = request.client.host if request.client else None

    # Check existence and password
    if user is None or not verify_password(credentials.password, user.hashed_password):
        await log_audit_event(
            db=db,
            action="login",
            outcome="deny",
            details={"email": credentials.email, "reason": "invalid_credentials"},
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check active status
    if not user.is_active:
        await log_audit_event(
            db=db,
            actor_user_id=user.id,
            action="login",
            outcome="deny",
            details="inactive_account",
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue access token
    access_token = create_access_token(user.id)
    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    await log_audit_event(
        db=db,
        actor_user_id=user.id,
        action="login",
        outcome="allow",
        ip_address=ip_address,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
    description="Returns the server-verified profile, roles, and department of the authenticated user.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """Return verified user profile derived strictly from server records."""
    return UserRead.model_validate(current_user)

"""Administrative routes for user management and security audit trail."""

from typing import Annotated, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin, get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventRead
from app.schemas.user import UserRead

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get(
    "/users",
    response_model=List[UserRead],
    summary="List all users",
    description="Returns all registered users with their roles and department assignments. Requires admin privileges.",
)
async def list_users(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> List[UserRead]:
    """Retrieve all users across departments for system administrators."""
    stmt = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.department))
        .order_by(User.created_at.asc())
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/audit-logs",
    response_model=List[AuditEventRead],
    summary="List audit events",
    description="Returns immutable security audit log entries. Requires admin privileges.",
)
async def list_audit_logs(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[AuditEventRead]:
    """Retrieve recent security audit log events."""
    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [AuditEventRead.model_validate(e) for e in events]

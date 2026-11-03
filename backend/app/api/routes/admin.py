"""Administrative routes for user management, security audit trail, and governance access review."""

import uuid
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin, get_db
from app.core.policy_codes import PolicyReasonCode
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import (
    AccessReviewReport,
    AuditEventRead,
    AuditExportResponse,
    AuditIntegrityReport,
)
from app.schemas.user import UserRead
from app.services.audit import (
    export_audit_trail,
    get_access_review,
    log_audit_event,
    verify_audit_trail_integrity,
)

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
    description="Returns immutable security audit log entries with optional filtering. Requires admin privileges.",
)
async def list_audit_logs(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    action: Optional[str] = Query(None, description="Filter by event action"),
    outcome: Optional[str] = Query(None, description="Filter by event outcome"),
    policy_reason_code: Optional[str] = Query(None, description="Filter by policy reason code"),
    actor_user_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[AuditEventRead]:
    """Retrieve filtered security audit log events with self-auditing telemetry."""
    stmt = select(AuditEvent)

    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    if policy_reason_code:
        stmt = stmt.where(AuditEvent.policy_reason_code == policy_reason_code)
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)

    stmt = (
        stmt.order_by(AuditEvent.sequence_number.desc().nullslast(), AuditEvent.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    # Self-audit log inspection when viewing the first page of audit logs
    if offset == 0:
        await log_audit_event(
            db=db,
            action="view_audit_logs",
            outcome="success",
            actor_user_id=admin_user.id,
            policy_reason_code=PolicyReasonCode.AUDIT_ACCESS_REVIEWED,
            resource_type="audit_log",
            details={"retrieved_count": len(events), "filter_action": action, "filter_outcome": outcome},
        )

    return [AuditEventRead.model_validate(e) for e in events]


@router.get(
    "/audit/integrity",
    response_model=AuditIntegrityReport,
    summary="Verify audit trail cryptographic hash-chain",
    description="Validates that no audit records have been altered, dropped, or inserted out of order. Requires admin privileges.",
)
async def verify_audit_integrity(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuditIntegrityReport:
    """Execute cryptographic hash chain verification across all recorded audit events."""
    report = await verify_audit_trail_integrity(db)

    # Self-audit verification attempt
    await log_audit_event(
        db=db,
        action="verify_audit_integrity",
        outcome="success" if report.is_valid else "failure",
        actor_user_id=admin_user.id,
        policy_reason_code=(
            PolicyReasonCode.AUDIT_INTEGRITY_VERIFIED
            if report.is_valid
            else PolicyReasonCode.AUDIT_TAMPER_DETECTED
        ),
        resource_type="audit_trail",
        details={
            "is_valid": report.is_valid,
            "total_events_checked": report.total_events_checked,
            "tampered_count": len(report.tampered_event_ids),
        },
    )

    return report


@router.get(
    "/access-review",
    response_model=AccessReviewReport,
    summary="Access review dashboard",
    description="Returns governance review data: roles, explicit grants, and security policy denials. Requires admin privileges.",
)
async def review_access_governance(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessReviewReport:
    """Generate governance access review report for administrators and compliance auditors."""
    report = await get_access_review(db)

    # Self-audit review generation
    await log_audit_event(
        db=db,
        action="review_access_policies",
        outcome="success",
        actor_user_id=admin_user.id,
        policy_reason_code=PolicyReasonCode.AUDIT_ACCESS_REVIEWED,
        resource_type="governance_review",
        details={"roles_count": len(report.roles_summary), "grants_count": len(report.explicit_grants)},
    )

    return report


@router.get(
    "/audit/export",
    response_model=AuditExportResponse,
    summary="Export audit trail",
    description="Controlled export of tamper-evident audit records. Requires admin privileges.",
)
async def export_audit_records(
    admin_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> AuditExportResponse:
    """Export audit records with cryptographic chain head signature."""
    return await export_audit_trail(db=db, actor_user_id=admin_user.id, limit=limit, offset=offset)

"""Audit logging and governance service for security, compliance, cryptographic hash-chaining, and access review."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger, request_id_ctx_var
from app.core.policy_codes import PolicyReasonCode
from app.models.audit import AuditEvent
from app.models.department import Department
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.models.role import Role
from app.models.user import User
from app.schemas.audit import (
    AccessReviewReport,
    AuditEventRead,
    AuditExportResponse,
    AuditIntegrityReport,
    DenialReviewItem,
    GrantReviewItem,
    RoleReviewItem,
)

logger = get_logger(__name__)

# Sensitive keys that must be redacted from audit details
SENSITIVE_AUDIT_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "file_bytes",
    "content",
    "raw_text",
    "passage",
    "chunk_text",
    "prompt",
}

GENESIS_HASH = "0" * 64


def compute_event_hash(
    event_id: uuid.UUID | str,
    sequence_number: int,
    actor_user_id: uuid.UUID | str | None,
    action: str,
    resource_id: str | None,
    outcome: str,
    policy_reason_code: str | None,
    timestamp: datetime,
    previous_event_hash: str,
) -> str:
    """Compute deterministic SHA-256 hash for an audit event link in the chain."""
    e_id = str(event_id)
    actor_str = str(actor_user_id) if actor_user_id else ""
    act = str(action)
    res_str = str(resource_id) if resource_id else ""
    out_str = str(outcome)
    p_code = str(policy_reason_code) if policy_reason_code else ""
    
    if hasattr(timestamp, "strftime"):
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts_str = str(timestamp)[:19]
    prev_h = previous_event_hash or GENESIS_HASH

    payload = f"{e_id}|{sequence_number}|{actor_str}|{act}|{res_str}|{out_str}|{p_code}|{ts_str}|{prev_h}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sanitize_details(details: Any) -> str | None:
    """Sanitize detail payloads to avoid logging passwords, secrets, credentials, or document excerpts."""
    if details is None:
        return None
    if isinstance(details, dict):
        sanitized = {}
        for k, v in details.items():
            if str(k).lower() in SENSITIVE_AUDIT_KEYS:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, str) and len(v) > 200:
                # Truncate long strings to prevent accidental text excerpt leakage
                sanitized[k] = v[:200] + "... [TRUNCATED]"
            else:
                sanitized[k] = v
        return json.dumps(sanitized)
    if isinstance(details, str):
        lower_str = details.lower()
        if any(sec in lower_str for sec in ("bearer ", "password=", "secret=", "api_key=")):
            return "[REDACTED_SENSITIVE_PAYLOAD]"
        if len(details) > 300:
            return details[:300] + "... [TRUNCATED]"
        return details
    return str(details)


async def log_audit_event(
    db: AsyncSession,
    action: str,
    outcome: str,
    actor_user_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    resource_type: str | None = None,
    policy_reason_code: str | None = None,
    details: Any = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    """Persist a cryptographically hash-chained, immutable audit log entry."""
    req_id = request_id or request_id_ctx_var.get()
    sanitized_details = _sanitize_details(details)
    event_id = uuid.uuid4()
    now_ts = datetime.now(timezone.utc)

    # Determine previous hash and sequence number in the chain
    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.sequence_number.desc().nullslast(), AuditEvent.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest_event = result.scalars().first()

    if latest_event and latest_event.sequence_number is not None:
        next_seq = latest_event.sequence_number + 1
        prev_hash = latest_event.event_hash or GENESIS_HASH
    else:
        next_seq = 1
        prev_hash = GENESIS_HASH

    curr_hash = compute_event_hash(
        event_id=event_id,
        sequence_number=next_seq,
        actor_user_id=actor_user_id,
        action=action,
        resource_id=resource_id,
        outcome=outcome,
        policy_reason_code=policy_reason_code,
        timestamp=now_ts,
        previous_event_hash=prev_hash,
    )

    event = AuditEvent(
        id=event_id,
        actor_user_id=actor_user_id,
        action=action,
        outcome=outcome,
        policy_reason_code=policy_reason_code,
        sequence_number=next_seq,
        previous_event_hash=prev_hash,
        event_hash=curr_hash,
        resource_id=str(resource_id) if resource_id else None,
        resource_type=resource_type,
        details=sanitized_details,
        ip_address=ip_address,
        request_id=req_id if req_id != "-" else None,
        timestamp=now_ts,
    )

    db.add(event)
    try:
        await db.commit()
        await db.refresh(event)
    except Exception as exc:
        logger.error("Failed to commit audit event %s: %s", action, str(exc))
        await db.rollback()
        raise

    return event


async def verify_audit_trail_integrity(db: AsyncSession) -> AuditIntegrityReport:
    """Reconstruct and verify the full cryptographic hash-chain across all recorded audit events."""
    stmt = select(AuditEvent).order_by(AuditEvent.sequence_number.asc().nullslast(), AuditEvent.timestamp.asc())
    result = await db.execute(stmt)
    events = result.scalars().all()

    if not events:
        return AuditIntegrityReport(
            is_valid=True,
            total_events_checked=0,
            tampered_event_ids=[],
            error_details=[],
            genesis_hash=GENESIS_HASH,
            chain_head_hash=None,
            verified_at=datetime.now(timezone.utc),
        )

    expected_prev_hash = GENESIS_HASH
    tampered_ids: List[str] = []
    errors: List[str] = []
    expected_seq = 1

    for event in events:
        eid_str = str(event.id)

        # 1. Check sequence monotonicity if sequence numbers are present
        if event.sequence_number is not None and event.sequence_number != expected_seq:
            errors.append(
                f"Event {eid_str} sequence broken: expected {expected_seq}, found {event.sequence_number}"
            )
            tampered_ids.append(eid_str)

        # 2. Check previous hash pointer
        if event.previous_event_hash != expected_prev_hash:
            errors.append(
                f"Event {eid_str} previous hash mismatch: expected {expected_prev_hash[:12]}..., found {str(event.previous_event_hash)[:12]}..."
            )
            tampered_ids.append(eid_str)

        # 3. Recompute expected event hash
        seq = event.sequence_number or expected_seq
        prev_h = event.previous_event_hash or expected_prev_hash
        recomputed = compute_event_hash(
            event_id=event.id,
            sequence_number=seq,
            actor_user_id=event.actor_user_id,
            action=event.action,
            resource_id=event.resource_id,
            outcome=event.outcome,
            policy_reason_code=event.policy_reason_code,
            timestamp=event.timestamp,
            previous_event_hash=prev_h,
        )

        if event.event_hash != recomputed:
            errors.append(
                f"Event {eid_str} payload hash mismatch (tampering detected): recorded {str(event.event_hash)[:12]}..., computed {recomputed[:12]}..."
            )
            tampered_ids.append(eid_str)

        expected_prev_hash = event.event_hash or recomputed
        expected_seq = seq + 1

    is_valid = len(tampered_ids) == 0
    return AuditIntegrityReport(
        is_valid=is_valid,
        total_events_checked=len(events),
        tampered_event_ids=list(dict.fromkeys(tampered_ids)),
        error_details=errors,
        genesis_hash=GENESIS_HASH,
        chain_head_hash=events[-1].event_hash if events else None,
        verified_at=datetime.now(timezone.utc),
    )


async def get_access_review(db: AsyncSession) -> AccessReviewReport:
    """Generate a comprehensive governance access review of roles, explicit grants, and security denials."""
    # 1. Roles summary
    role_stmt = select(Role).options(selectinload(Role.users))
    role_res = await db.execute(role_stmt)
    roles = role_res.scalars().all()

    roles_summary: List[RoleReviewItem] = []
    for r in roles:
        perms = []
        if r.name == "admin":
            perms = ["admin:*", "documents:*", "users:*", "grants:*", "audit:*"]
        elif r.name == "manager":
            perms = [
                "documents:read_dept",
                "documents:upload_dept",
                "documents:read_confidential_dept",
                "grants:manage_dept",
                "feedback:review_dept",
            ]
        else:
            perms = ["documents:read_standard_dept", "feedback:submit", "chat:query"]

        roles_summary.append(
            RoleReviewItem(
                role_id=str(r.id),
                role_name=r.name,
                description=r.description,
                users_count=len(r.users),
                permissions=perms,
            )
        )

    # 2. Explicit grants
    grant_stmt = (
        select(DocumentGrant)
        .options(
            selectinload(DocumentGrant.document),
            selectinload(DocumentGrant.grantee_user),
            selectinload(DocumentGrant.grantee_role),
        )
        .join(Document, Document.id == DocumentGrant.document_id)
        .where(Document.status != "deleted", Document.lifecycle_state != "deleted")
        .order_by(DocumentGrant.created_at.desc())
    )
    grant_res = await db.execute(grant_stmt)
    grants = grant_res.scalars().all()

    dept_stmt = select(Department)
    dept_res = await db.execute(dept_stmt)
    depts = {d.id: d.name for d in dept_res.scalars().all()}

    explicit_grants: List[GrantReviewItem] = []
    privilege_anomalies: List[str] = []

    for g in grants:
        doc = g.document
        dept_name = depts.get(doc.department_id, "Unknown") if doc else "Unknown"
        doc_title = doc.title if doc else "Unknown Document"

        if g.grantee_user_id:
            grantee_type = "user"
            grantee_id = str(g.grantee_user_id)
            grantee_label = g.grantee_user.email if g.grantee_user else f"User {grantee_id[:8]}"
            # Anomaly check: cross-department user grant
            if (
                g.grantee_user
                and g.grantee_user.department_id
                and doc
                and doc.department_id
                and g.grantee_user.department_id != doc.department_id
            ):
                user_dept = depts.get(g.grantee_user.department_id, "External")
                privilege_anomalies.append(
                    f"Cross-department grant: {grantee_label} ({user_dept}) has explicit grant on {doc_title} ({dept_name})"
                )
        else:
            grantee_type = "role"
            grantee_id = str(g.grantee_role_id)
            grantee_label = g.grantee_role.name if g.grantee_role else f"Role {grantee_id[:8]}"

        explicit_grants.append(
            GrantReviewItem(
                grant_id=str(g.id),
                document_id=str(g.document_id),
                document_title=doc_title,
                department_name=dept_name,
                grantee_type=grantee_type,
                grantee_id=grantee_id,
                grantee_label=grantee_label,
                permission=g.permission,
                created_at=g.created_at,
            )
        )

    # 3. Recent policy denials
    denial_stmt = (
        select(AuditEvent)
        .where(
            or_(
                AuditEvent.outcome.in_(["denied", "forbidden", "failure"]),
                AuditEvent.policy_reason_code.like("%_DENIED"),
            )
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(25)
    )
    denial_res = await db.execute(denial_stmt)
    denials = denial_res.scalars().all()

    recent_denials: List[DenialReviewItem] = []
    for d in denials:
        recent_denials.append(
            DenialReviewItem(
                timestamp=d.timestamp,
                action=d.action,
                actor_user_id=str(d.actor_user_id) if d.actor_user_id else None,
                policy_reason_code=d.policy_reason_code,
                resource_id=d.resource_id,
                safe_explanation=d.details or "Access rejected by security policy",
            )
        )

    return AccessReviewReport(
        roles_summary=roles_summary,
        explicit_grants=explicit_grants,
        recent_denials=recent_denials,
        privilege_anomalies=privilege_anomalies,
        generated_at=datetime.now(timezone.utc),
    )


async def export_audit_trail(
    db: AsyncSession,
    actor_user_id: uuid.UUID,
    limit: int = 500,
    offset: int = 0,
) -> AuditExportResponse:
    """Controlled export of audit trail, logging the export event for compliance."""
    export_id = str(uuid.uuid4())
    now_ts = datetime.now(timezone.utc)

    # 1. Self-audit the export action first so that this export event is recorded in the chain
    await log_audit_event(
        db=db,
        action="export_audit_trail",
        outcome="success",
        actor_user_id=actor_user_id,
        policy_reason_code=PolicyReasonCode.AUDIT_LOGS_EXPORTED,
        resource_id=export_id,
        resource_type="audit_export",
        details={"requested_limit": limit},
    )

    # 2. Fetch events including the export audit record
    stmt = (
        select(AuditEvent)
        .order_by(AuditEvent.sequence_number.asc().nullslast(), AuditEvent.timestamp.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    events = res.scalars().all()
    chain_head = events[-1].event_hash if events else None

    return AuditExportResponse(
        export_id=export_id,
        exported_at=now_ts,
        exported_by_user_id=str(actor_user_id),
        total_events=len(events),
        chain_head_hash=chain_head,
        events=[AuditEventRead.model_validate(e) for e in events],
    )

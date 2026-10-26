"""Audit logging service for security, compliance, and authorization events."""

import json
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, request_id_ctx_var
from app.models.audit import AuditEvent

logger = get_logger(__name__)

# Sensitive keys that must be redacted from audit details
SENSITIVE_AUDIT_KEYS = {"password", "token", "secret", "api_key", "authorization", "access_token"}


def _sanitize_details(details: Any) -> str | None:
    """Sanitize detail payloads to avoid logging passwords or raw secrets."""
    if details is None:
        return None
    if isinstance(details, dict):
        sanitized = {}
        for k, v in details.items():
            if str(k).lower() in SENSITIVE_AUDIT_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return json.dumps(sanitized)
    if isinstance(details, str):
        return details
    return str(details)


async def log_audit_event(
    db: AsyncSession,
    action: str,
    outcome: str,
    actor_user_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    resource_type: str | None = None,
    details: Any = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    """Persist an immutable audit log entry into the database."""
    req_id = request_id or request_id_ctx_var.get()
    sanitized_details = _sanitize_details(details)

    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        outcome=outcome,
        resource_id=str(resource_id) if resource_id else None,
        resource_type=resource_type,
        details=sanitized_details,
        ip_address=ip_address,
        request_id=req_id if req_id != "-" else None,
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

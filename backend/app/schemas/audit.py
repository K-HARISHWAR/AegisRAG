"""AuditEvent and Governance Pydantic schemas."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditEventRead(BaseModel):
    """Audit event representation for compliance reporting."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    outcome: str
    policy_reason_code: Optional[str] = None
    sequence_number: Optional[int] = None
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime


class AuditIntegrityReport(BaseModel):
    """Cryptographic hash-chain integrity verification report."""

    is_valid: bool = Field(..., description="Whether all cryptographic hash links in the audit chain are valid and untampered.")
    total_events_checked: int = Field(default=0, description="Total audit events evaluated.")
    tampered_event_ids: List[str] = Field(default_factory=list, description="IDs of any events where the payload or hash was altered.")
    error_details: List[str] = Field(default_factory=list, description="Diagnostic descriptions of broken chains or payload mutations.")
    genesis_hash: str = Field(default="0" * 64, description="Genesis anchor hash.")
    chain_head_hash: Optional[str] = Field(default=None, description="Current latest hash link.")
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp when verification completed.")


class RoleReviewItem(BaseModel):
    """Role breakdown for governance review."""

    role_id: str
    role_name: str
    description: Optional[str] = None
    users_count: int
    permissions: List[str] = Field(default_factory=list)


class GrantReviewItem(BaseModel):
    """Active explicit document grant entry."""

    grant_id: str
    document_id: str
    document_title: str
    department_name: str
    grantee_type: str  # "user" | "role"
    grantee_id: str
    grantee_label: str
    permission: str
    created_at: datetime


class DenialReviewItem(BaseModel):
    """Recent security policy denial telemetry entry."""

    timestamp: datetime
    action: str
    actor_user_id: Optional[str] = None
    policy_reason_code: Optional[str] = None
    resource_id: Optional[str] = None
    safe_explanation: Optional[str] = None


class AccessReviewReport(BaseModel):
    """Comprehensive access review report for administrators and auditors."""

    roles_summary: List[RoleReviewItem] = Field(default_factory=list)
    explicit_grants: List[GrantReviewItem] = Field(default_factory=list)
    recent_denials: List[DenialReviewItem] = Field(default_factory=list)
    privilege_anomalies: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditExportResponse(BaseModel):
    """Controlled audit trail export artifact."""

    export_id: str
    exported_at: datetime
    exported_by_user_id: str
    total_events: int
    chain_head_hash: Optional[str] = None
    events: List[AuditEventRead] = Field(default_factory=list)


class PolicyDecisionExplanation(BaseModel):
    """Safe, sanitized policy explanation revealing minimal necessary details without leaking protected content."""

    allowed: bool
    policy_reason_code: str
    safe_explanation: str
    resource_id: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

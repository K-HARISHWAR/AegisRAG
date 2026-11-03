"""Unit, integration, and security tests for Phase 17 Governance, Audit Trail, and Policy Explanations."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy_codes import PolicyReasonCode
from app.models.audit import AuditEvent
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.schemas.audit import AuditIntegrityReport, PolicyDecisionExplanation
from app.services.audit import compute_event_hash, log_audit_event, verify_audit_trail_integrity
from app.services.policy import explain_denial
from tests.conftest import get_auth_header


def test_grant_and_revoke_produce_audit_events_with_reason_codes(client: TestClient, seeded_db: dict) -> None:
    """Security/Audit: Grant and revoke actions generate structured immutable events with policy reason codes."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    alice = users["alice@example.com"]  # Engineering Employee
    docs = {d.title: d for d in seeded_db["documents"]}
    runbook_doc = docs["engineering_runbook.pdf"]

    admin_headers = get_auth_header(admin.id)

    # 1. Admin creates an explicit grant for Alice
    grant_payload = {
        "grantee_user_id": str(alice.id),
        "permission": "read",
    }
    create_res = client.post(
        f"/api/v1/documents/{runbook_doc.id}/grants",
        json=grant_payload,
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    grant_data = create_res.json()
    grant_id = grant_data["id"]

    # 2. Verify audit event for grant creation
    audit_res = client.get("/api/v1/admin/audit-logs?limit=5", headers=admin_headers)
    assert audit_res.status_code == 200
    events = audit_res.json()

    create_events = [e for e in events if e["action"] == "create_grant" and e["resource_id"] == grant_id]
    assert len(create_events) >= 1
    create_evt = create_events[0]
    assert create_evt["outcome"] == "allow"
    assert create_evt["policy_reason_code"] == PolicyReasonCode.GRANT_CREATED
    assert create_evt["sequence_number"] is not None
    assert create_evt["event_hash"] is not None

    # 3. Admin revokes the explicit grant
    revoke_res = client.delete(
        f"/api/v1/documents/{runbook_doc.id}/grants/{grant_id}",
        headers=admin_headers,
    )
    assert revoke_res.status_code == 200

    # 4. Verify audit event for grant revocation
    audit_res2 = client.get("/api/v1/admin/audit-logs?limit=5", headers=admin_headers)
    assert audit_res2.status_code == 200
    events2 = audit_res2.json()

    revoke_events = [e for e in events2 if e["action"] == "revoke_grant" and e["resource_id"] == grant_id]
    assert len(revoke_events) >= 1
    revoke_evt = revoke_events[0]
    assert revoke_evt["outcome"] == "allow"
    assert revoke_evt["policy_reason_code"] == PolicyReasonCode.GRANT_REVOKED


def test_unauthorized_user_cannot_view_audit_records(client: TestClient, seeded_db: dict) -> None:
    """Security: Employees and unauthorized roles are strictly forbidden from viewing audit records (403)."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]  # Engineering Employee
    alice_headers = get_auth_header(alice.id)

    # 1. Audit logs listing
    res_logs = client.get("/api/v1/admin/audit-logs", headers=alice_headers)
    assert res_logs.status_code == 403

    # 2. Access review
    res_review = client.get("/api/v1/admin/access-review", headers=alice_headers)
    assert res_review.status_code == 403

    # 3. Hash integrity check
    res_integrity = client.get("/api/v1/admin/audit/integrity", headers=alice_headers)
    assert res_integrity.status_code == 403

    # 4. Audit export
    res_export = client.get("/api/v1/admin/audit/export", headers=alice_headers)
    assert res_export.status_code == 403


def test_audit_logs_contain_no_excerpts_credentials_or_api_keys(client: TestClient, seeded_db: dict) -> None:
    """Security/Redaction: Audit logs scrub credentials, passwords, raw file bytes, and prompts."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]

    # 1. Trigger a failed login with a password that should be redacted
    fake_password = "SuperSecretPlainTextPassword123!"
    client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": fake_password},
    )

    # 2. Inspect recorded audit log entries
    admin_headers = get_auth_header(admin.id)
    res = client.get("/api/v1/admin/audit-logs?limit=50", headers=admin_headers)
    assert res.status_code == 200
    events = res.json()

    for evt in events:
        details_str = str(evt.get("details") or "")
        # The plaintext password must NEVER appear anywhere in the details
        assert fake_password not in details_str
        assert "SuperSecretPlainTextPassword" not in details_str

        # General sensitive tokens must never appear unredacted
        assert "bearer " not in details_str.lower()
        assert "api_key=" not in details_str.lower()


@pytest.mark.asyncio
async def test_hash_chaining_integrity_verification_detects_tampering(db_session: AsyncSession) -> None:
    """Security: Cryptographic hash chaining verification detects modified records immediately."""
    # 1. Verify clean initial chain
    report = await verify_audit_trail_integrity(db_session)
    assert report.is_valid is True
    assert len(report.tampered_event_ids) == 0

    # 2. Log two legitimate chained events
    actor_id = uuid.uuid4()
    evt1 = await log_audit_event(
        db=db_session,
        action="user_login",
        outcome="allow",
        actor_user_id=actor_id,
        policy_reason_code="AUTH_SUCCESS",
    )
    evt2 = await log_audit_event(
        db=db_session,
        action="view_document",
        outcome="allow",
        actor_user_id=actor_id,
        policy_reason_code="DOC_READ_PERMITTED",
        resource_id="doc-xyz",
    )

    # Verify chain after logging
    report2 = await verify_audit_trail_integrity(db_session)
    assert report2.is_valid is True

    # 3. Simulate an attacker directly tampering with an audit record in the database
    # Attacker attempts to change "outcome" of evt1 from "allow" to "deny"
    await db_session.execute(
        update(AuditEvent)
        .where(AuditEvent.id == evt1.id)
        .values(outcome="denied_by_attacker")
    )
    await db_session.commit()

    # 4. Verify integrity detects the tampering!
    tampered_report = await verify_audit_trail_integrity(db_session)
    assert tampered_report.is_valid is False
    assert str(evt1.id) in tampered_report.tampered_event_ids
    assert any("tampering detected" in err for err in tampered_report.error_details)


def test_denial_explanation_leaks_no_restricted_content(client: TestClient, seeded_db: dict) -> None:
    """Security: Policy denial explanation reveals minimal necessary rationale without exposing restricted content."""
    users = {u.email: u for u in seeded_db["users"]}
    bob = users["bob@example.com"]  # HR Employee
    docs = {d.title: d for d in seeded_db["documents"]}
    runbook_doc = docs["engineering_runbook.pdf"]

    bob_headers = get_auth_header(bob.id)

    # Bob (HR) requests an access explanation on the Engineering Runbook
    res = client.get(
        f"/api/v1/documents/{runbook_doc.id}/explain-access",
        headers=bob_headers,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["allowed"] is False
    assert data["policy_reason_code"] == PolicyReasonCode.DEPT_MISMATCH_DENIED
    assert "department boundary policy" in data["safe_explanation"]

    # Verify no confidential content, passages, or runbook contents leaked
    assert "Kubernetes" not in data["safe_explanation"]
    assert "PostgreSQL" not in data["safe_explanation"]
    assert "disaster recovery" not in data["safe_explanation"]


def test_access_review_and_self_auditing(client: TestClient, seeded_db: dict) -> None:
    """Governance: Access review returns roles, grants, and security denials, while self-auditing the review action."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    admin_headers = get_auth_header(admin.id)

    # 1. Fetch access review
    res = client.get("/api/v1/admin/access-review", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert "roles_summary" in data
    assert len(data["roles_summary"]) >= 3  # admin, manager, employee
    assert "explicit_grants" in data
    assert "recent_denials" in data
    assert "privilege_anomalies" in data

    # 2. Verify that reviewing access was self-audited
    audit_res = client.get("/api/v1/admin/audit-logs?limit=50", headers=admin_headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert any(
        e["action"] == "review_access_policies" and e["policy_reason_code"] == PolicyReasonCode.AUDIT_ACCESS_REVIEWED
        for e in events
    )


def test_controlled_audit_export(client: TestClient, seeded_db: dict) -> None:
    """Governance: Controlled export returns signed audit records and self-audits the export."""
    users = {u.email: u for u in seeded_db["users"]}
    admin = users["admin@example.com"]
    admin_headers = get_auth_header(admin.id)

    # 1. Request export
    res = client.get("/api/v1/admin/audit/export?limit=100", headers=admin_headers)
    assert res.status_code == 200
    export_data = res.json()

    assert "export_id" in export_data
    assert export_data["exported_by_user_id"] == str(admin.id)
    assert export_data["total_events"] > 0
    assert len(export_data["events"]) > 0

    # 2. Verify self-audit of export
    audit_res = client.get("/api/v1/admin/audit-logs?limit=50", headers=admin_headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert any(
        e["action"] == "export_audit_trail" and e["policy_reason_code"] == PolicyReasonCode.AUDIT_LOGS_EXPORTED
        for e in events
    )

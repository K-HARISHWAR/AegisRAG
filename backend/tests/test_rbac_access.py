"""Integration tests proving cross-department isolation, default-deny RBAC, and client tamper-proofing."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from tests.conftest import get_auth_header


def test_cross_department_access_denied_to_employee(
    client: TestClient, seeded_db: dict
) -> None:
    """Verify an employee cannot access another department's document by guessing its ID."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    alice = users["alice@example.com"]  # Engineering
    doc_comp = docs["executive_compensation_2026.xlsx"]  # HR

    headers = get_auth_header(alice.id)
    response = client.get(f"/api/v1/documents/{doc_comp.id}", headers=headers)

    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_confidential_document_in_own_department_denied_to_employee(
    client: TestClient, seeded_db: dict
) -> None:
    """Verify an employee cannot access confidential documents in their own department without a grant."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    alice = users["alice@example.com"]  # Engineering
    doc_secrets = docs["infra_secrets_master.docx"]  # Engineering, confidential

    headers = get_auth_header(alice.id)
    response = client.get(f"/api/v1/documents/{doc_secrets.id}", headers=headers)

    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_explicit_document_grant_allows_access(
    client: TestClient, seeded_db: dict
) -> None:
    """Verify explicit DocumentGrant in PostgreSQL overrides cross-department restriction."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    alice = users["alice@example.com"]  # Engineering
    doc_leave = docs["leave_policy.pdf"]  # HR (granted to Alice)

    headers = get_auth_header(alice.id)
    response = client.get(f"/api/v1/documents/{doc_leave.id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "leave_policy.pdf"
    assert len(data["grants"]) == 1


def test_unknown_document_id_returns_404(client: TestClient, seeded_db: dict) -> None:
    """Verify non-existent document ID returns HTTP 404."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]

    headers = get_auth_header(alice.id)
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/documents/{fake_id}", headers=headers)

    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]


def test_manager_accesses_own_dept_confidential_but_denied_cross_dept(
    client: TestClient, seeded_db: dict
) -> None:
    """Verify department managers can access own confidential docs but not other departments'."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    charlie = users["charlie@example.com"]  # Eng Manager
    doc_secrets = docs["infra_secrets_master.docx"]  # Eng confidential
    doc_comp = docs["executive_compensation_2026.xlsx"]  # HR confidential

    headers = get_auth_header(charlie.id)

    # Own department confidential: 200 OK
    res_own = client.get(f"/api/v1/documents/{doc_secrets.id}", headers=headers)
    assert res_own.status_code == 200

    # Cross-department confidential: 403 Forbidden
    res_cross = client.get(f"/api/v1/documents/{doc_comp.id}", headers=headers)
    assert res_cross.status_code == 403


def test_altered_client_supplied_role_claims_ignored(
    client: TestClient, seeded_db: dict
) -> None:
    """Verify client-supplied headers or claims pretending to be admin or manager are strictly ignored."""
    users = {u.email: u for u in seeded_db["users"]}
    alice = users["alice@example.com"]  # standard employee

    # Alice attempts to spoof admin privileges using fake headers
    spoofed_headers = get_auth_header(alice.id)
    spoofed_headers.update({
        "X-Role": "admin",
        "X-User-Role": "admin",
        "X-Is-Superuser": "true",
        "X-Department": "HR",
    })

    # 1. Attempt admin endpoint: must be 403 Forbidden
    res_admin = client.get("/api/v1/admin/users", headers=spoofed_headers)
    assert res_admin.status_code == 403
    assert "Insufficient administrative privileges" in res_admin.json()["detail"]

    # 2. Attempt unauthorized document: must still be 403 Forbidden
    docs = {d.title: d for d in seeded_db["documents"]}
    doc_comp = docs["executive_compensation_2026.xlsx"]
    res_doc = client.get(f"/api/v1/documents/{doc_comp.id}", headers=spoofed_headers)
    assert res_doc.status_code == 403


def test_document_upload_permissions(client: TestClient, seeded_db: dict) -> None:
    """Verify managers can upload only to their assigned department, employees cannot upload."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    alice = users["alice@example.com"]      # Eng Employee
    charlie = users["charlie@example.com"]  # Eng Manager
    eng_id = depts["Engineering"].id
    hr_id = depts["HR"].id

    payload_eng = {
        "title": "new_architecture_rfc.pdf",
        "department_id": str(eng_id),
        "file_type": "pdf",
        "file_size_bytes": 2048,
        "checksum_sha256": "abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd",
        "is_confidential": False,
    }

    # 1. Alice (employee) attempts upload to Engineering: 403 Forbidden
    res_alice = client.post("/api/v1/documents", json=payload_eng, headers=get_auth_header(alice.id))
    assert res_alice.status_code == 403

    # 2. Charlie (Eng Manager) uploads to Engineering: 201 Created
    res_charlie_eng = client.post("/api/v1/documents", json=payload_eng, headers=get_auth_header(charlie.id))
    assert res_charlie_eng.status_code == 201
    assert res_charlie_eng.json()["title"] == "new_architecture_rfc.pdf"

    # 3. Charlie attempts upload to HR: 403 Forbidden
    payload_hr = payload_eng.copy()
    payload_hr["department_id"] = str(hr_id)
    res_charlie_hr = client.post("/api/v1/documents", json=payload_hr, headers=get_auth_header(charlie.id))
    assert res_charlie_hr.status_code == 403


def test_admin_full_access_and_audit_log_inspection(
    client: TestClient, seeded_db: dict
) -> None:
    """Verify administrator has full cross-department access and can inspect audit events."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}
    admin = users["admin@example.com"]

    admin_headers = get_auth_header(admin.id)

    # 1. Admin accesses HR confidential document
    doc_comp = docs["executive_compensation_2026.xlsx"]
    res_doc = client.get(f"/api/v1/documents/{doc_comp.id}", headers=admin_headers)
    assert res_doc.status_code == 200

    # 2. Admin inspects users
    res_users = client.get("/api/v1/admin/users", headers=admin_headers)
    assert res_users.status_code == 200
    assert len(res_users.json()) == 6

    # 3. Admin inspects audit logs
    res_audit = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert res_audit.status_code == 200
    events = res_audit.json()
    assert len(events) > 0
    # Confirm outcomes exist in audit log
    outcomes = {e["outcome"] for e in events}
    assert "allow" in outcomes


@pytest.mark.asyncio
async def test_audit_event_logged_on_denial(
    client: TestClient, seeded_db: dict, db_session: AsyncSession
) -> None:
    """Verify unauthorized document access creates an audit log entry with outcome='deny'."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    alice = users["alice@example.com"]
    doc_comp = docs["executive_compensation_2026.xlsx"]

    # Trigger denial
    response = client.get(f"/api/v1/documents/{doc_comp.id}", headers=get_auth_header(alice.id))
    assert response.status_code == 403

    # Inspect audit log directly from DB
    stmt = select(AuditEvent).where(
        AuditEvent.actor_user_id == alice.id,
        AuditEvent.action == "read_document",
        AuditEvent.outcome == "deny",
    )
    result = await db_session.execute(stmt)
    denied_events = result.scalars().all()
    assert len(denied_events) >= 1
    assert denied_events[0].resource_id == str(doc_comp.id)

"""Unit tests for centralized authorization policy logic."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.policy import (
    can_manage_grants,
    can_manage_users,
    can_read_document,
    can_upload_document,
    get_authorized_document_ids,
)


@pytest.mark.asyncio
async def test_can_manage_users(seeded_db: dict) -> None:
    """Verify only active admin users can manage system users."""
    users = {u.email: u for u in seeded_db["users"]}

    assert can_manage_users(users["admin@example.com"]) is True
    assert can_manage_users(users["charlie@example.com"]) is False
    assert can_manage_users(users["alice@example.com"]) is False
    assert can_manage_users(users["inactive@example.com"]) is False


@pytest.mark.asyncio
async def test_can_upload_document(seeded_db: dict) -> None:
    """Verify department upload restrictions for admin, manager, employee, and inactive."""
    users = {u.email: u for u in seeded_db["users"]}
    depts = {d.name: d for d in seeded_db["departments"]}

    eng_id = depts["Engineering"].id
    hr_id = depts["HR"].id

    admin = users["admin@example.com"]
    charlie = users["charlie@example.com"]  # Eng Manager
    alice = users["alice@example.com"]      # Eng Employee
    inactive = users["inactive@example.com"]

    # Admin can upload to any department
    assert can_upload_document(admin, eng_id) is True
    assert can_upload_document(admin, hr_id) is True

    # Department manager can upload ONLY to their assigned department
    assert can_upload_document(charlie, eng_id) is True
    assert can_upload_document(charlie, hr_id) is False

    # Employees and inactive users cannot upload
    assert can_upload_document(alice, eng_id) is False
    assert can_upload_document(alice, hr_id) is False
    assert can_upload_document(inactive, eng_id) is False


@pytest.mark.asyncio
async def test_can_read_document_default_deny(seeded_db: dict, db_session: AsyncSession) -> None:
    """Verify cross-department isolation, confidential restrictions, and explicit grant overrides."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    alice = users["alice@example.com"]       # Eng Employee
    charlie = users["charlie@example.com"]   # Eng Manager
    admin = users["admin@example.com"]
    inactive = users["inactive@example.com"]

    doc_runbook = docs["engineering_runbook.pdf"]          # Eng, public
    doc_secrets = docs["infra_secrets_master.docx"]        # Eng, confidential
    doc_leave = docs["leave_policy.pdf"]                  # HR, public, explicitly granted to Alice
    doc_comp = docs["executive_compensation_2026.xlsx"]     # HR, confidential

    # 1. Alice (Eng Employee)
    # Own department public: ALLOW
    assert await can_read_document(alice, doc_runbook, db_session) is True
    # Own department confidential without grant: DENY
    assert await can_read_document(alice, doc_secrets, db_session) is False
    # Cross-department confidential without grant: DENY
    assert await can_read_document(alice, doc_comp, db_session) is False
    # Cross-department public WITH explicit grant: ALLOW
    assert await can_read_document(alice, doc_leave, db_session) is True

    # 2. Charlie (Eng Manager)
    # Own department public: ALLOW
    assert await can_read_document(charlie, doc_runbook, db_session) is True
    # Own department confidential: ALLOW (Manager privilege in own dept)
    assert await can_read_document(charlie, doc_secrets, db_session) is True
    # Cross-department confidential without grant: DENY
    assert await can_read_document(charlie, doc_comp, db_session) is False

    # 3. Admin: ALLOW all
    assert await can_read_document(admin, doc_runbook, db_session) is True
    assert await can_read_document(admin, doc_secrets, db_session) is True
    assert await can_read_document(admin, doc_leave, db_session) is True
    assert await can_read_document(admin, doc_comp, db_session) is True

    # 4. Inactive user: DENY all
    assert await can_read_document(inactive, doc_runbook, db_session) is False


@pytest.mark.asyncio
async def test_deleted_document_access_denied(seeded_db: dict, db_session: AsyncSession) -> None:
    """Verify soft-deleted documents fail closed for all users including admins."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    admin = users["admin@example.com"]
    doc = docs["engineering_runbook.pdf"]
    doc.status = "deleted"
    db_session.add(doc)
    await db_session.commit()

    assert await can_read_document(admin, doc, db_session) is False


@pytest.mark.asyncio
async def test_get_authorized_document_ids(seeded_db: dict, db_session: AsyncSession) -> None:
    """Verify pre-retrieval filter IDs match expected access permissions."""
    users = {u.email: u for u in seeded_db["users"]}
    docs = {d.title: d for d in seeded_db["documents"]}

    alice = users["alice@example.com"]
    charlie = users["charlie@example.com"]
    admin = users["admin@example.com"]
    inactive = users["inactive@example.com"]

    doc_runbook = docs["engineering_runbook.pdf"]
    doc_secrets = docs["infra_secrets_master.docx"]
    doc_leave = docs["leave_policy.pdf"]
    doc_comp = docs["executive_compensation_2026.xlsx"]

    # Alice should see Eng runbook + HR leave (grant)
    alice_ids = set(await get_authorized_document_ids(alice, db_session))
    assert doc_runbook.id in alice_ids
    assert doc_leave.id in alice_ids
    assert doc_secrets.id not in alice_ids
    assert doc_comp.id not in alice_ids

    # Charlie (Eng Manager) should see both Eng docs
    charlie_ids = set(await get_authorized_document_ids(charlie, db_session))
    assert doc_runbook.id in charlie_ids
    assert doc_secrets.id in charlie_ids
    assert doc_comp.id not in charlie_ids

    # Admin should see all 4 documents
    admin_ids = set(await get_authorized_document_ids(admin, db_session))
    assert len(admin_ids) == 4

    # Inactive user sees none
    inactive_ids = await get_authorized_document_ids(inactive, db_session)
    assert len(inactive_ids) == 0

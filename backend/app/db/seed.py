"""Seed data script for development and testing environments."""

import asyncio
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.base import Base
from app.models.department import Department
from app.models.document import Document
from app.models.grant import DocumentGrant
from app.models.role import Role
from app.models.user import User


async def seed_database(db: AsyncSession) -> dict[str, Any]:
    """Populate database with synthetic departments, roles, users, and documents."""
    # 1. Departments
    dept_eng = Department(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Engineering",
        description="Software engineering, infrastructure, and DevOps",
    )
    dept_hr = Department(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        name="HR",
        description="Human resources, payroll, and benefits",
    )
    db.add_all([dept_eng, dept_hr])
    await db.flush()

    # 2. Roles
    role_emp = Role(
        id=uuid.UUID("33333333-3333-3333-3333-333333333331"),
        name="employee",
        description="Standard employee role with department-level access",
    )
    role_mgr = Role(
        id=uuid.UUID("33333333-3333-3333-3333-333333333332"),
        name="department_manager",
        description="Department manager role with upload and document grant permissions",
    )
    role_admin = Role(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        name="admin",
        description="Global administrator role with unrestricted tenant access",
    )
    db.add_all([role_emp, role_mgr, role_admin])
    await db.flush()

    default_pw = hash_password("TestPass123!")

    # 3. Users
    user_alice = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444441"),
        email="alice@example.com",
        hashed_password=default_pw,
        department_id=dept_eng.id,
        is_active=True,
        roles=[role_emp],
    )
    user_bob = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444442"),
        email="bob@example.com",
        hashed_password=default_pw,
        department_id=dept_hr.id,
        is_active=True,
        roles=[role_emp],
    )
    user_charlie = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444443"),
        email="charlie@example.com",
        hashed_password=default_pw,
        department_id=dept_eng.id,
        is_active=True,
        roles=[role_mgr],
    )
    user_diana = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        email="diana@example.com",
        hashed_password=default_pw,
        department_id=dept_hr.id,
        is_active=True,
        roles=[role_mgr],
    )
    user_admin = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444445"),
        email="admin@example.com",
        hashed_password=default_pw,
        department_id=None,
        is_active=True,
        is_superuser=True,
        roles=[role_admin],
    )
    user_inactive = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444446"),
        email="inactive@example.com",
        hashed_password=default_pw,
        department_id=dept_eng.id,
        is_active=False,
        roles=[role_emp],
    )
    db.add_all([user_alice, user_bob, user_charlie, user_diana, user_admin, user_inactive])
    await db.flush()

    # 4. Documents
    doc_runbook = Document(
        id=uuid.UUID("55555555-5555-5555-5555-555555555551"),
        title="engineering_runbook.pdf",
        owner_id=user_charlie.id,
        department_id=dept_eng.id,
        storage_key="doc_runbook_eng",
        file_type="pdf",
        file_size_bytes=1048576,
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_confidential=False,
        status="indexed",
    )
    doc_secrets = Document(
        id=uuid.UUID("55555555-5555-5555-5555-555555555552"),
        title="infra_secrets_master.docx",
        owner_id=user_charlie.id,
        department_id=dept_eng.id,
        storage_key="doc_secrets_eng",
        file_type="docx",
        file_size_bytes=524288,
        checksum_sha256="cbf529a4d5d44708510b64bf204e380277712738b156d6d82c667ceb70fa0a59",
        is_confidential=True,
        status="indexed",
    )
    doc_leave = Document(
        id=uuid.UUID("55555555-5555-5555-5555-555555555553"),
        title="leave_policy.pdf",
        owner_id=user_diana.id,
        department_id=dept_hr.id,
        storage_key="doc_leave_hr",
        file_type="pdf",
        file_size_bytes=786432,
        checksum_sha256="8b1a9953c4611296a827abf8c47804d7ecd3c491f3697926306537a5734f4125",
        is_confidential=False,
        status="indexed",
    )
    doc_compensation = Document(
        id=uuid.UUID("55555555-5555-5555-5555-555555555554"),
        title="executive_compensation_2026.xlsx",
        owner_id=user_diana.id,
        department_id=dept_hr.id,
        storage_key="doc_comp_hr",
        file_type="xlsx",
        file_size_bytes=262144,
        checksum_sha256="7d793037a0760186574b0282f2f435e70d63ee33b66804bb0f205eb0bf6122d2",
        is_confidential=True,
        status="indexed",
    )
    db.add_all([doc_runbook, doc_secrets, doc_leave, doc_compensation])
    await db.flush()

    # 5. Document Grants: Grant Alice explicit read access to HR's leave_policy.pdf
    grant_alice_leave = DocumentGrant(
        id=uuid.UUID("66666666-6666-6666-6666-666666666661"),
        document_id=doc_leave.id,
        grantee_user_id=user_alice.id,
        permission="read",
        granted_by_user_id=user_diana.id,
    )
    db.add(grant_alice_leave)
    await db.commit()

    return {
        "departments": [dept_eng, dept_hr],
        "roles": [role_emp, role_mgr, role_admin],
        "users": [user_alice, user_bob, user_charlie, user_diana, user_admin, user_inactive],
        "documents": [doc_runbook, doc_secrets, doc_leave, doc_compensation],
        "grants": [grant_alice_leave],
    }


async def main() -> None:
    """Standalone entry point to seed database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_database(session)
    print("Database schema created and synthetic test data seeded successfully.")


if __name__ == "__main__":
    from typing import Any
    asyncio.run(main())

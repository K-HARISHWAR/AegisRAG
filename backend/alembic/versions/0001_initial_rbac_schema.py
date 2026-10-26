"""0001_initial_rbac_schema

Revision ID: 0001_initial_rbac_schema
Revises: 
Create Date: 2026-10-26 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "0001_initial_rbac_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. departments
    op.create_table(
        "departments",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_departments_name", "departments", ["name"])

    # 2. roles
    op.create_table(
        "roles",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_roles_name", "roles", ["name"])

    # 3. users
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("department_id", GUID(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_department_id", "users", ["department_id"])

    # 4. user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("role_id", GUID(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )

    # 5. documents
    op.create_table(
        "documents",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("owner_id", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", GUID(), sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("is_confidential", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_department_id", "documents", ["department_id"])
    op.create_index("ix_documents_storage_key", "documents", ["storage_key"])
    op.create_index("ix_documents_checksum_sha256", "documents", ["checksum_sha256"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # 6. document_grants
    op.create_table(
        "document_grants",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantee_user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("grantee_role_id", GUID(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("permission", sa.String(30), nullable=False, server_default="read"),
        sa.Column("granted_by_user_id", GUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "grantee_user_id IS NOT NULL OR grantee_role_id IS NOT NULL",
            name="check_grantee_specified",
        ),
    )
    op.create_index("ix_document_grants_document_id", "document_grants", ["document_id"])
    op.create_index("ix_document_grants_grantee_user_id", "document_grants", ["grantee_user_id"])
    op.create_index("ix_document_grants_grantee_role_id", "document_grants", ["grantee_role_id"])

    # 7. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("actor_user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("document_grants")
    op.drop_table("documents")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("departments")

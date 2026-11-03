"""0005_governance_audit_hash_chain

Revision ID: 0005_governance_audit_hash_chain
Revises: 0004_conversation_threads_and_memory
Create Date: 2026-11-03 20:45:00.000000

"""
import hashlib
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_governance_audit_hash_chain"
down_revision: Union[str, None] = "0004_conversation_threads_and_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("audit_events"):
        cols = [c["name"] for c in insp.get_columns("audit_events")]

        if "policy_reason_code" not in cols:
            op.add_column("audit_events", sa.Column("policy_reason_code", sa.String(64), nullable=True))
            op.create_index("ix_audit_events_policy_reason_code", "audit_events", ["policy_reason_code"])

        if "sequence_number" not in cols:
            op.add_column("audit_events", sa.Column("sequence_number", sa.BigInteger(), nullable=True))
            op.create_index("ix_audit_events_sequence_number", "audit_events", ["sequence_number"])

        if "previous_event_hash" not in cols:
            op.add_column("audit_events", sa.Column("previous_event_hash", sa.String(64), nullable=True))

        if "event_hash" not in cols:
            op.add_column("audit_events", sa.Column("event_hash", sa.String(64), nullable=True))
            op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"])

        # Backfill existing audit events with monotonic sequence numbers and hash chain
        try:
            conn = op.get_bind()
            audit_events_meta = sa.Table(
                "audit_events",
                sa.MetaData(),
                sa.Column("id", sa.String),
                sa.Column("actor_user_id", sa.String),
                sa.Column("action", sa.String),
                sa.Column("resource_id", sa.String),
                sa.Column("outcome", sa.String),
                sa.Column("policy_reason_code", sa.String),
                sa.Column("timestamp", sa.DateTime),
                sa.Column("sequence_number", sa.BigInteger),
                sa.Column("previous_event_hash", sa.String),
                sa.Column("event_hash", sa.String),
            )
            rows = conn.execute(sa.select(audit_events_meta).order_by(audit_events_meta.c.timestamp.asc())).fetchall()
            if rows:
                prev_hash = "0" * 64
                for idx, row in enumerate(rows, start=1):
                    row_id = str(row.id)
                    actor_str = str(row.actor_user_id) if row.actor_user_id else ""
                    action_str = str(row.action)
                    res_str = str(row.resource_id) if row.resource_id else ""
                    outcome_str = str(row.outcome)
                    p_code = str(row.policy_reason_code) if row.policy_reason_code else ""
                    ts_str = row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp)

                    payload = f"{row_id}|{idx}|{actor_str}|{action_str}|{res_str}|{outcome_str}|{p_code}|{ts_str}|{prev_hash}"
                    curr_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

                    conn.execute(
                        audit_events_meta.update()
                        .where(audit_events_meta.c.id == row.id)
                        .values(
                            sequence_number=idx,
                            previous_event_hash=prev_hash,
                            event_hash=curr_hash,
                        )
                    )
                    prev_hash = curr_hash
        except Exception:
            # Tolerant on empty or fresh schema
            pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("audit_events"):
        cols = [c["name"] for c in insp.get_columns("audit_events")]
        if "event_hash" in cols:
            op.drop_index("ix_audit_events_event_hash", table_name="audit_events")
            op.drop_column("audit_events", "event_hash")
        if "previous_event_hash" in cols:
            op.drop_column("audit_events", "previous_event_hash")
        if "sequence_number" in cols:
            op.drop_index("ix_audit_events_sequence_number", table_name="audit_events")
            op.drop_column("audit_events", "sequence_number")
        if "policy_reason_code" in cols:
            op.drop_index("ix_audit_events_policy_reason_code", table_name="audit_events")
            op.drop_column("audit_events", "policy_reason_code")

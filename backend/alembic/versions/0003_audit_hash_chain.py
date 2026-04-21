"""Add prev_hash + event_hash columns to audit_events (POR-158 #7 hash chain).

Revision: 0003
Previous: 0002

Columns
    prev_hash   : VARCHAR(64) NULL      (sha256 hex of previous event, or NULL for genesis)
    event_hash  : VARCHAR(64) NULL      (sha256 hex of this event's canonical payload)

event_hash is added as NULL because existing rows (if any) pre-date the chain
and cannot be retro-hashed without rewriting them in order. For fresh
environments (all test runs, the staging reset after this migration lands),
every row will have event_hash populated. A one-off backfill script can be
added later if we decide to preserve pre-chain history.

Indexes
    ix_audit_events_event_hash  (non-unique)  — used by verification walks and
                                                 the `_get_latest_hash` probe
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_events",
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("event_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_audit_events_event_hash",
        "audit_events",
        ["event_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_hash", table_name="audit_events")
    op.drop_column("audit_events", "event_hash")
    op.drop_column("audit_events", "prev_hash")

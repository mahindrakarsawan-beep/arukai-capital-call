"""v0.2 state machine migration (POR-147 / ARU-17-B1).

Revision: 0001
Previous: None (initial migration — creates v0.2 schema from v0.1 SQLAlchemy-managed tables)

Changes:
1. Expand user_role enum: add 'approver'
2. Add package_state enum column on packages (6 states)
3. Rename status → legacy_status on packages
4. Add version, claimed_by_user_id, claimed_at, exception_reason, last_moved_at on packages
5. Data migration: map v0.1 status values to v0.2 states (per spec §2.3)
   - pending_classification → submitted
   - pending_review + confidence ≥ 0.5 → intake_complete
   - pending_review + confidence < 0.5 → exception_surfaced   (R12: NULL treated as 0.0)
   - approved → decision_recorded
   - rejected → decision_recorded
6. Add version=1 to all existing rows
7. Create reviewer_notes table
8. Drop unique constraint on classifications.document_id, add is_current bool
9. Add extracted_fields JSON on classifications
10. Drop unique constraint on approvals.package_id, add is_final bool
11. Fix audit_events.package_id ondelete to RESTRICT (R10)
12. Add indexes for audit performance (R11)
13. PostgreSQL: add append-only trigger on audit_events (R9)
    SQLite: guard is at Python application layer (test-only)
14. Add legacy_status generated-equivalent column note in comments (R13)
"""
import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _is_sqlite(connection) -> bool:
    return connection.dialect.name == "sqlite"


def _is_postgresql(connection) -> bool:
    return connection.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = _is_sqlite(bind)
    is_pg = _is_postgresql(bind)

    # -----------------------------------------------------------------------
    # 1. Expand user_role enum to include 'approver'
    # -----------------------------------------------------------------------
    if is_pg:
        op.execute(text("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'approver'"))
    # SQLite: enum is stored as VARCHAR — no ALTER TYPE needed; model change is enough

    # -----------------------------------------------------------------------
    # 2–4. Packages table changes
    #       SQLite requires batch mode for ALTER COLUMN
    # -----------------------------------------------------------------------
    with op.batch_alter_table("packages") as batch_op:
        # Rename status → legacy_status (R13)
        batch_op.alter_column("status", new_column_name="legacy_status")

        # Add v0.2 state column (nullable initially for data migration)
        batch_op.add_column(
            sa.Column(
                "state",
                sa.Enum(
                    "submitted", "intake_complete", "under_review",
                    "routed_for_approval", "decision_recorded", "exception_surfaced",
                    name="package_state",
                ),
                nullable=True,
            )
        )

        # Optimistic locking version (R2)
        batch_op.add_column(
            sa.Column("version", sa.Integer, nullable=True, default=1)
        )

        # Claim model (S1)
        batch_op.add_column(
            sa.Column(
                "claimed_by_user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True)
        )

        # Exception reason
        batch_op.add_column(
            sa.Column(
                "exception_reason",
                sa.Enum(
                    "low_confidence", "missing_field", "extraction_failure",
                    name="exception_reason_enum",
                ),
                nullable=True,
            )
        )

        # Last state movement timestamp
        batch_op.add_column(
            sa.Column("last_moved_at", sa.DateTime(timezone=True), nullable=True)
        )

    # -----------------------------------------------------------------------
    # 5. Data migration: map v0.1 status → v0.2 state
    # -----------------------------------------------------------------------
    # R12: NULL confidence treated as 0.0 → exception_surfaced
    # Use a JOIN to get classification confidence for pending_review packages.
    #
    # SQLite / PostgreSQL compatible SQL:
    # pending_classification → submitted
    bind.execute(text("""
        UPDATE packages
        SET state = 'submitted',
            version = 1,
            last_moved_at = updated_at
        WHERE legacy_status = 'pending_classification'
    """))

    # approved → decision_recorded
    bind.execute(text("""
        UPDATE packages
        SET state = 'decision_recorded',
            version = 1,
            last_moved_at = updated_at
        WHERE legacy_status = 'approved'
    """))

    # rejected → decision_recorded
    bind.execute(text("""
        UPDATE packages
        SET state = 'decision_recorded',
            version = 1,
            last_moved_at = updated_at
        WHERE legacy_status = 'rejected'
    """))

    # pending_review: use JOIN with classifications via documents
    # R12: treat NULL confidence as 0.0 (COALESCE)
    if is_sqlite:
        bind.execute(text("""
            UPDATE packages
            SET state = CASE
                WHEN (
                    SELECT COALESCE(c.confidence, 0.0)
                    FROM documents d
                    LEFT JOIN classifications c ON c.document_id = d.id
                    WHERE d.package_id = packages.id
                    ORDER BY c.created_at DESC
                    LIMIT 1
                ) >= 0.5 THEN 'intake_complete'
                ELSE 'exception_surfaced'
            END,
            exception_reason = CASE
                WHEN (
                    SELECT COALESCE(c.confidence, 0.0)
                    FROM documents d
                    LEFT JOIN classifications c ON c.document_id = d.id
                    WHERE d.package_id = packages.id
                    ORDER BY c.created_at DESC
                    LIMIT 1
                ) >= 0.5 THEN NULL
                ELSE 'low_confidence'
            END,
            version = 1,
            last_moved_at = updated_at
            WHERE legacy_status = 'pending_review'
        """))
    else:
        # PostgreSQL: LATERAL join
        bind.execute(text("""
            UPDATE packages p
            SET state = CASE
                WHEN COALESCE(latest_clf.confidence, 0.0) >= 0.5 THEN 'intake_complete'::package_state
                ELSE 'exception_surfaced'::package_state
            END,
            exception_reason = CASE
                WHEN COALESCE(latest_clf.confidence, 0.0) >= 0.5 THEN NULL
                ELSE 'low_confidence'::exception_reason_enum
            END,
            version = 1,
            last_moved_at = p.updated_at
            FROM (
                SELECT d.package_id,
                       c.confidence
                FROM documents d
                LEFT JOIN classifications c ON c.document_id = d.id
                WHERE c.id = (
                    SELECT c2.id FROM classifications c2
                    WHERE c2.document_id = d.id
                    ORDER BY c2.created_at DESC
                    LIMIT 1
                )
            ) AS latest_clf
            WHERE p.id = latest_clf.package_id
            AND p.legacy_status = 'pending_review'
        """))

    # Packages with no documents at all (edge case): mark as exception_surfaced
    bind.execute(text("""
        UPDATE packages
        SET state = 'exception_surfaced',
            exception_reason = 'extraction_failure',
            version = 1,
            last_moved_at = updated_at
        WHERE legacy_status = 'pending_review'
        AND state IS NULL
    """))

    # Any remaining NULLs (shouldn't happen but be safe)
    bind.execute(text("""
        UPDATE packages
        SET state = 'submitted', version = 1, last_moved_at = updated_at
        WHERE state IS NULL
    """))
    bind.execute(text("""
        UPDATE packages SET version = 1 WHERE version IS NULL
    """))

    # -----------------------------------------------------------------------
    # 6. Make state and version NOT NULL now that data is populated
    # -----------------------------------------------------------------------
    with op.batch_alter_table("packages") as batch_op:
        batch_op.alter_column("state", nullable=False)
        batch_op.alter_column("version", nullable=False, server_default="1")
        # Add index on state
        batch_op.create_index("ix_packages_state", ["state"])
        batch_op.create_index("ix_packages_last_moved_at", ["last_moved_at"])

    # -----------------------------------------------------------------------
    # 7. Classifications: remove unique constraint on document_id, add is_current
    # -----------------------------------------------------------------------
    # Drop unique constraint first (outside batch) — Postgres-specific; SQLite batch handles via recreate
    if is_pg:
        # Find and drop any unique constraint on document_id (name may vary)
        bind.execute(text("""
            DO $$
            DECLARE
                con_name text;
            BEGIN
                SELECT conname INTO con_name FROM pg_constraint
                WHERE conrelid = 'classifications'::regclass
                  AND contype = 'u'
                  AND array_length(conkey, 1) = 1
                  AND conkey[1] = (SELECT attnum FROM pg_attribute WHERE attrelid = 'classifications'::regclass AND attname = 'document_id');
                IF con_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE classifications DROP CONSTRAINT %I', con_name);
                END IF;
            END $$;
        """))

    with op.batch_alter_table("classifications") as batch_op:
        # Add is_current flag
        batch_op.add_column(
            sa.Column("is_current", sa.Boolean, nullable=True, default=True)
        )
        # Add extracted_fields JSON column
        batch_op.add_column(
            sa.Column("extracted_fields", sa.JSON, nullable=True)
        )

    # Backfill is_current = True for all existing rows (only one row per doc anyway)
    if is_pg:
        bind.execute(text("UPDATE classifications SET is_current = TRUE WHERE is_current IS NULL"))
    else:
        bind.execute(text("UPDATE classifications SET is_current = 1 WHERE is_current IS NULL"))

    with op.batch_alter_table("classifications") as batch_op:
        batch_op.alter_column("is_current", nullable=False, server_default="1")

    # -----------------------------------------------------------------------
    # 8. Approvals: drop unique constraint on package_id, add is_final
    # -----------------------------------------------------------------------
    if is_pg:
        bind.execute(text("""
            DO $$
            DECLARE
                con_name text;
            BEGIN
                SELECT conname INTO con_name FROM pg_constraint
                WHERE conrelid = 'approvals'::regclass
                  AND contype = 'u'
                  AND array_length(conkey, 1) = 1
                  AND conkey[1] = (SELECT attnum FROM pg_attribute WHERE attrelid = 'approvals'::regclass AND attname = 'package_id');
                IF con_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE approvals DROP CONSTRAINT %I', con_name);
                END IF;
            END $$;
        """))

    with op.batch_alter_table("approvals") as batch_op:
        batch_op.add_column(
            sa.Column("is_final", sa.Boolean, nullable=True, default=True)
        )

    if is_pg:
        bind.execute(text("UPDATE approvals SET is_final = TRUE WHERE is_final IS NULL"))
    else:
        bind.execute(text("UPDATE approvals SET is_final = 1 WHERE is_final IS NULL"))

    with op.batch_alter_table("approvals") as batch_op:
        batch_op.alter_column("is_final", nullable=False, server_default="1")

    # -----------------------------------------------------------------------
    # 9. Create reviewer_notes table (R5)
    # -----------------------------------------------------------------------
    op.create_table(
        "reviewer_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "package_id",
            sa.String(36),
            sa.ForeignKey("packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "supersedes_note_id",
            sa.String(36),
            sa.ForeignKey("reviewer_notes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_reviewer_notes_package_id", "reviewer_notes", ["package_id"])
    op.create_index("ix_reviewer_notes_author_user_id", "reviewer_notes", ["author_user_id"])

    # -----------------------------------------------------------------------
    # 10. Audit events: add indexes (R11) and fix ondelete to RESTRICT (R10)
    # -----------------------------------------------------------------------
    # Add composite indexes for audit query performance
    op.create_index(
        "ix_audit_events_actor_created",
        "audit_events",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_action_created",
        "audit_events",
        ["action", "created_at"],
    )
    op.create_index(
        "ix_audit_events_created_at",
        "audit_events",
        ["created_at"],
    )

    # Fix audit_events.package_id ondelete from SET NULL → RESTRICT (R10)
    # In SQLite batch mode this recreates the table with the new FK constraint
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_constraint("fk_audit_events_package_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_audit_events_package_id",
            "packages",
            ["package_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # -----------------------------------------------------------------------
    # 11. PostgreSQL: append-only trigger on audit_events (R9)
    # -----------------------------------------------------------------------
    if is_pg:
        op.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_audit_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql;
        """))
        op.execute(text("""
            CREATE TRIGGER no_update_delete_audit_events
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();
        """))
    # SQLite: Python-level guard is in app/audit_guard.py (test-only enforcement)


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = _is_postgresql(bind)

    # Drop append-only trigger (PostgreSQL)
    if is_pg:
        op.execute(text("DROP TRIGGER IF EXISTS no_update_delete_audit_events ON audit_events"))
        op.execute(text("DROP FUNCTION IF EXISTS prevent_audit_mutation()"))

    # Restore audit_events FK to SET NULL
    with op.batch_alter_table("audit_events") as batch_op:
        try:
            batch_op.drop_constraint("fk_audit_events_package_id", type_="foreignkey")
        except Exception:
            pass
        batch_op.create_foreign_key(
            "fk_audit_events_package_id",
            "packages",
            ["package_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Drop new audit indexes
    op.drop_index("ix_audit_events_actor_created", "audit_events")
    op.drop_index("ix_audit_events_action_created", "audit_events")
    op.drop_index("ix_audit_events_created_at", "audit_events")

    # Drop reviewer_notes table
    op.drop_table("reviewer_notes")

    # Restore approvals unique constraint
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.drop_column("is_final")
        batch_op.create_unique_constraint("uq_approvals_package_id", ["package_id"])

    # Restore classifications unique constraint and drop new columns
    with op.batch_alter_table("classifications") as batch_op:
        batch_op.drop_column("extracted_fields")
        batch_op.drop_column("is_current")
        batch_op.create_unique_constraint("uq_classifications_document_id", ["document_id"])

    # Restore packages to v0.1 shape
    with op.batch_alter_table("packages") as batch_op:
        try:
            batch_op.drop_index("ix_packages_state")
            batch_op.drop_index("ix_packages_last_moved_at")
        except Exception:
            pass
        batch_op.drop_column("last_moved_at")
        batch_op.drop_column("exception_reason")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("claimed_by_user_id")
        batch_op.drop_column("version")
        batch_op.drop_column("state")
        batch_op.alter_column("legacy_status", new_column_name="status")

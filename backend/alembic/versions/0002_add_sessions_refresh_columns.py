"""Add sessions.refresh_token_hash + sessions.refresh_expires_at (Sprint 8-10 drift fix).

Revision: 0002
Previous: 0001 (v0.2 state machine)

The columns exist in SQLAlchemy model (backend/app/models.py Session class) since
commit 42ccee6 but the migration was never written. Staging DB (running rev 18
of v0.2.1-final image) lacks them, so any session query with these columns in
the SELECT list fails with asyncpg UndefinedColumnError → login 500.

Changes:
1. ALTER TABLE sessions ADD COLUMN refresh_token_hash VARCHAR(64) NULL
2. ALTER TABLE sessions ADD COLUMN refresh_expires_at TIMESTAMP WITH TIME ZONE NULL
3. CREATE INDEX ix_sessions_refresh_token_hash ON sessions (refresh_token_hash)
   (non-unique; matches mapped_column(..., index=True) without unique=True)

Downgrade is supported and removes both columns + the index.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "refresh_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sessions_refresh_token_hash",
        "sessions",
        ["refresh_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_refresh_token_hash", table_name="sessions")
    op.drop_column("sessions", "refresh_expires_at")
    op.drop_column("sessions", "refresh_token_hash")

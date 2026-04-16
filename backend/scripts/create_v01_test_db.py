"""Script to create a v0.1 test database for verifying the Alembic migration.

Usage:
    cd backend
    python -m scripts.create_v01_test_db
    python -m alembic -x dbpath=./migration_test_v01.db upgrade head

This script creates a migration_test_v01.db with v0.1 schema and sample data,
then you can run alembic upgrade head against it to test the v0.1 → v0.2 migration.
"""
import datetime
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DB_PATH = "./migration_test_v01.db"


def create_v01_db(path: str = DB_PATH):
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    now = datetime.datetime.utcnow().isoformat()

    with engine.connect() as conn:
        # Create v0.1 schema
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'reviewer',
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS packages (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, uploaded_by TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_classification',
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, package_id TEXT NOT NULL, filename TEXT NOT NULL,
                mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                content BLOB NOT NULL, created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS classifications (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL UNIQUE,
                document_type TEXT NOT NULL, confidence REAL NOT NULL,
                key_indicators TEXT, model_version TEXT, fallback INTEGER NOT NULL,
                classification_error TEXT, created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY, package_id TEXT NOT NULL UNIQUE,
                decided_by TEXT NOT NULL, decision TEXT NOT NULL,
                note TEXT, decided_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY, package_id TEXT, actor_user_id TEXT,
                action TEXT NOT NULL, before_state TEXT, after_state TEXT,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE, expires_at DATETIME NOT NULL,
                revoked_at DATETIME
            )
        """))

        # Seed user
        uid = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO users VALUES ('{uid}', 'admin@arukai.example', 'hashed', 'admin', '{now}')"
        ))

        # 1. pending_classification → submitted
        p1 = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO packages VALUES ('{p1}', 'Pending Classification Test', '{uid}', "
            f"'pending_classification', '{now}', '{now}')"
        ))

        # 2. pending_review + high confidence → intake_complete
        p2 = str(uuid.uuid4())
        d2 = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO packages VALUES ('{p2}', 'High Confidence Review', '{uid}', "
            f"'pending_review', '{now}', '{now}')"
        ))
        conn.execute(text(
            f"INSERT INTO documents VALUES ('{d2}', '{p2}', 'doc.pdf', 'application/pdf', 100, x'504446', '{now}')"
        ))
        conn.execute(text(
            f"INSERT INTO classifications VALUES ('{str(uuid.uuid4())}', '{d2}', "
            f"'capital_call_notice', 0.92, NULL, NULL, 0, NULL, '{now}')"
        ))

        # 3. pending_review + low confidence → exception_surfaced
        p3 = str(uuid.uuid4())
        d3 = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO packages VALUES ('{p3}', 'Low Confidence Review', '{uid}', "
            f"'pending_review', '{now}', '{now}')"
        ))
        conn.execute(text(
            f"INSERT INTO documents VALUES ('{d3}', '{p3}', 'doc.pdf', 'application/pdf', 100, x'504446', '{now}')"
        ))
        conn.execute(text(
            f"INSERT INTO classifications VALUES ('{str(uuid.uuid4())}', '{d3}', "
            f"'other', 0.2, NULL, NULL, 1, NULL, '{now}')"
        ))

        # 4. approved → decision_recorded
        p4 = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO packages VALUES ('{p4}', 'Approved Package', '{uid}', "
            f"'approved', '{now}', '{now}')"
        ))
        conn.execute(text(
            f"INSERT INTO approvals VALUES ('{str(uuid.uuid4())}', '{p4}', '{uid}', "
            f"'approved', 'Looks good', '{now}')"
        ))

        # 5. rejected → decision_recorded
        p5 = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO packages VALUES ('{p5}', 'Rejected Package', '{uid}', "
            f"'rejected', '{now}', '{now}')"
        ))
        conn.execute(text(
            f"INSERT INTO approvals VALUES ('{str(uuid.uuid4())}', '{p5}', '{uid}', "
            f"'rejected', 'Insufficient docs', '{now}')"
        ))

        # 6. pending_review + NULL confidence → exception_surfaced (R12)
        p6 = str(uuid.uuid4())
        conn.execute(text(
            f"INSERT INTO packages VALUES ('{p6}', 'NULL Confidence Test', '{uid}', "
            f"'pending_review', '{now}', '{now}')"
        ))
        # No classification row — simulates missing confidence (NULL → 0.0)

        conn.commit()

    print(f"Created v0.1 test DB: {path}")
    print("Run: python -m alembic upgrade head  (with DATABASE_URL pointing to this DB)")
    engine.dispose()


if __name__ == "__main__":
    create_v01_db()

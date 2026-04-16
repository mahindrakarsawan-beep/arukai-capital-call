"""Shared test fixtures v0.2 — in-memory SQLite DB + seeded test client.

Updated for v0.2 (POR-147 / ARU-17-B1):
- Uses in-memory SQLite (:memory:) to avoid stale schema issues
- async_session fixture for direct DB tests (depends on db_init to ensure tables exist)
- approver user seeded via main.py lifespan
- LegacyPackageFactory retained for migration path tests (R14)
"""
import os

import pytest
from fastapi.testclient import TestClient

# Force in-memory SQLite for tests — avoids stale file-DB schema issues
# Must be set before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")

from app.main import app  # noqa: E402 — must be after env setup


@pytest.fixture(scope="session")
def client():
    """TestClient that triggers lifespan (DB init + seed) once per session.

    Seeds admin@, reviewer@, and approver@ users via main.py _seed_dev_users().
    In-memory DB is fresh for each test session.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db_initialized(client):
    """Ensure DB tables + seed data exist before async tests run.

    Depends on client fixture so lifespan has run and init_db() has created
    all tables in the in-memory database.
    """
    return True


@pytest.fixture()
async def async_session(db_initialized):
    """Async DB session for direct DB access tests.

    Depends on db_initialized to ensure tables exist (init_db has run).
    Yields a session for raw SQL / ORM operations.
    Rolls back after each test to keep DB clean.
    """
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()

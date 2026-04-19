"""Shared test fixtures v0.2 — in-memory SQLite DB + seeded test client."""
import os

os.environ.setdefault("APP_ENV", "test")

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

"""Shared test fixtures — sets up in-memory SQLite DB + seeded test client."""
import asyncio
import os

import pytest
from fastapi.testclient import TestClient

# Use in-memory SQLite for tests (isolated per test session)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest")

from app.main import app  # noqa: E402 — must be after env setup


@pytest.fixture(scope="session")
def client():
    """TestClient that triggers lifespan (DB init + seed) once per session."""
    with TestClient(app) as c:
        yield c

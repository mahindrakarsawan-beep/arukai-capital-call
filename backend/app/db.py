"""Database engine and session setup — SQLAlchemy 2.0 async."""
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./dev.db",
)

# Neon Postgres uses postgresql:// — remap to async driver
_ssl = False
if DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg does not accept sslmode as a query param; strip it and use connect_args instead
    if "sslmode=require" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "").replace("&sslmode=require", "")
        _ssl = True
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    if "sslmode=require" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "").replace("&sslmode=require", "")
        _ssl = True

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
elif _ssl:
    import ssl as _ssl_mod
    _ssl_ctx = _ssl_mod.create_default_context()
    _connect_args = {"ssl": _ssl_ctx}

engine = create_async_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables on startup (v0.1 — no Alembic required for dev)."""
    from app import models  # noqa: F401 — ensure models are registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

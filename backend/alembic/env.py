"""Alembic environment — async SQLAlchemy support for Arukai Capital Call."""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config object
config = context.config

# Set up loggers
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models so that autogenerate can detect schema changes
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import Base  # noqa: E402

target_metadata = Base.metadata

# Read DATABASE_URL from environment (same as app/db.py)
_db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
# Strip sslmode query param — asyncpg rejects it; SSL handled via connect_args
if "?sslmode=" in _db_url:
    _db_url = _db_url.split("?sslmode=")[0]
# Normalize postgres:// → postgresql+asyncpg://
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# For synchronous alembic operations (offline mode), use sync driver
_sync_url = _db_url.replace("postgresql+asyncpg://", "postgresql://").replace("sqlite+aiosqlite://", "sqlite://")

config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async online mode."""
    import ssl
    from sqlalchemy.ext.asyncio import create_async_engine

    connect_args = {}
    if "postgresql+asyncpg://" in _db_url:
        connect_args["ssl"] = ssl.create_default_context()

    connectable = create_async_engine(
        _db_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # For SQLite (dev), use synchronous engine
    if _sync_url.startswith("sqlite://"):
        from sqlalchemy import create_engine
        connectable = create_engine(_sync_url, connect_args={"check_same_thread": False})
        with connectable.connect() as connection:
            do_run_migrations(connection)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

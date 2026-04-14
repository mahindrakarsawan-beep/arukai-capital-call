"""FastAPI app factory — Arukai Capital Call v0.1."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import approvals, auth, packages


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create all DB tables and seed dev users."""
    await init_db()
    await _seed_dev_users()
    yield


async def _seed_dev_users():
    """Create admin + reviewer seed users if they don't exist (idempotent)."""
    from sqlalchemy import select

    from app.auth import hash_password
    from app.db import AsyncSessionLocal
    from app.models import User

    async with AsyncSessionLocal() as db:
        for email, password, role in [
            ("admin@arukai.example", "admin123", "admin"),
            ("reviewer@arukai.example", "reviewer123", "reviewer"),
        ]:
            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing is None:
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                )
                db.add(user)
        await db.commit()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Arukai Capital Call API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router)
    application.include_router(packages.router)
    application.include_router(approvals.router)

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "capital-call"}

    return application


app = create_app()

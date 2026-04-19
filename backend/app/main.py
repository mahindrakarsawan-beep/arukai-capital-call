"""FastAPI app factory — Arukai Capital Call v0.2 (POR-147 / ARU-17-B1)."""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import approvals, auth
from app.routers.packages import (
    router as packages_router,
    legacy_router as packages_legacy_router,
    deprecation_router as approvals_deprecation_router,
)
from app.routers.audit import router as audit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create all DB tables and seed dev users."""
    await init_db()
    await _seed_dev_users()
    yield


async def _seed_dev_users():
    """Create seed users. Random passwords in production, deterministic in test."""
    import os
    import secrets
    from sqlalchemy import select

    from app.auth import hash_password
    from app.db import AsyncSessionLocal
    from app.models import User

    is_test = os.environ.get("APP_ENV") == "test" or "pytest" in sys.modules

    # Test uses deterministic passwords so tests can login.
    # Production uses cryptographically random passwords printed once.
    test_passwords = {
        "admin": "admin123",
        "reviewer": "reviewer123",
        "approver": "approver123",
    }

    async with AsyncSessionLocal() as db:
        for email, role in [
            ("admin@arukai.example", "admin"),
            ("reviewer@arukai.example", "reviewer"),
            ("approver@arukai.example", "approver"),
        ]:
            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing is None:
                password = test_passwords[role] if is_test else secrets.token_urlsafe(24)
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                )
                db.add(user)
                if not is_test:
                    print(f"[SEED] Created {role}: {email} / {password}")
        await db.commit()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Arukai Capital Call API",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    import os
    cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] or [
        "http://localhost:3000",
        "https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app",
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth
    application.include_router(auth.router)

    # Packages (new v0.2 canonical routes)
    application.include_router(packages_router)

    # Legacy /documents prefix — backward compatibility
    application.include_router(packages_legacy_router)

    # Deprecated approvals endpoint (410 bridge)
    application.include_router(approvals_deprecation_router)

    # Audit (global + per-package)
    application.include_router(audit_router)

    # Keep v0.1 approvals router for any remaining imports
    application.include_router(approvals.router)

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "capital-call", "version": "0.2.0"}

    return application


app = create_app()

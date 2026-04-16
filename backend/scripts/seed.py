"""Seed script v0.2 — creates dev users including approver role.

Usage:
    cd backend
    python -m scripts.seed

Credentials are dev-only and must NOT be used in production.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.auth import hash_password
from app.db import AsyncSessionLocal, init_db
from app.models import User


async def seed():
    print("Initialising database…")
    await init_db()

    seed_users = [
        ("admin@arukai.example", "admin123", "admin"),
        ("reviewer@arukai.example", "reviewer123", "reviewer"),
        ("approver@arukai.example", "approver123", "approver"),  # S2: new approver role
    ]

    async with AsyncSessionLocal() as db:
        for email, password, role in seed_users:
            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"  [SKIP] {email} already exists")
            else:
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                )
                db.add(user)
                print(f"  [CREATE] {email} ({role})")
        await db.commit()

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())

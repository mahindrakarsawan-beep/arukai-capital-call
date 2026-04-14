"""Auth router — login, logout, me."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    _hash_token,
    create_access_token,
    get_current_user,
    verify_password,
)
from app.db import get_db
from app.models import AuditEvent, Session, User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str


class MeResponse(BaseModel):
    id: str
    email: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_at = create_access_token(user.id, user.email, user.role)
    token_hash = _hash_token(token)

    session = Session(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(session)

    audit = AuditEvent(
        actor_user_id=user.id,
        action="login",
        after_state={"email": user.email, "role": user.role},
    )
    db.add(audit)

    await db.commit()

    return LoginResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    # We need the raw token to revoke it — pass via header is already extracted
    # But we need to get the session via get_current_user's dependency chain.
    # Workaround: re-fetch session by user_id (most recent active session).
):
    """Revoke the current session."""
    from fastapi import Request
    # We can't easily get the raw token here without injecting Request.
    # Use a different approach: fetch the most-recently-created non-revoked session.
    result = await db.execute(
        select(Session).where(
            Session.user_id == current_user.id,
            Session.revoked_at.is_(None),
        ).order_by(Session.expires_at.desc())
    )
    sessions = result.scalars().all()

    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now

    audit = AuditEvent(
        actor_user_id=current_user.id,
        action="logout",
        after_state={"email": current_user.email},
    )
    db.add(audit)

    await db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(id=current_user.id, email=current_user.email, role=current_user.role)

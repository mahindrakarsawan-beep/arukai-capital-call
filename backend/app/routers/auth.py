"""Auth router — login, logout, me, OIDC."""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    _hash_token,
    check_password_policy,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.audit_chain import create_audit_event
from app.db import get_db
from app.models import AuditEvent, Session, User

router = APIRouter(prefix="/auth", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
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

    # Upsert: if a session with this hash exists (same-second login), reuse/restore it
    from app.auth import create_refresh_token
    refresh_token, refresh_expires = create_refresh_token()
    refresh_hash = _hash_token(refresh_token)

    existing_result = await db.execute(
        select(Session).where(Session.token_hash == token_hash)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is None:
        session = Session(
            user_id=user.id,
            token_hash=token_hash,
            refresh_token_hash=refresh_hash,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires,
        )
        db.add(session)
    elif existing.revoked_at is not None:
        existing.revoked_at = None
        existing.expires_at = expires_at
        existing.refresh_token_hash = refresh_hash
        existing.refresh_expires_at = refresh_expires

    await create_audit_event(
        db,
        package_id=None,
        actor_user_id=user.id,
        action="login",
        after_state={"email": user.email, "role": user.role},
    )

    await db.commit()

    return LoginResponse(
        access_token=token,
        refresh_token=refresh_token,
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

    await create_audit_event(
        db,
        package_id=None,
        actor_user_id=current_user.id,
        action="logout",
        after_state={"email": current_user.email},
    )

    await db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(id=current_user.id, email=current_user.email, role=current_user.role)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    ok, reason = check_password_policy(body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    current_user.password_hash = hash_password(body.new_password)
    current_user.password_changed_at = datetime.now(timezone.utc)

    from app.auth import revoke_all_sessions
    await revoke_all_sessions(current_user.id, db)

    await create_audit_event(
        db,
        package_id=None,
        actor_user_id=current_user.id,
        action="password_changed",
        after_state={"email": current_user.email},
    )
    await db.commit()

    return {"message": "Password changed. All sessions revoked — please re-login."}


# ---------------------------------------------------------------------------
# OIDC integration (Keycloak / Zitadel)
# ---------------------------------------------------------------------------

class OIDCCallbackRequest(BaseModel):
    code: str


def _oidc_configured() -> bool:
    return all([
        os.environ.get("OIDC_ISSUER_URL"),
        os.environ.get("OIDC_CLIENT_ID"),
        os.environ.get("OIDC_CLIENT_SECRET"),
        os.environ.get("OIDC_REDIRECT_URI"),
    ])


def _map_oidc_role(userinfo: dict) -> str:
    """Map IdP groups/roles claim to local role. Default: reviewer."""
    valid = {"admin", "reviewer", "approver"}
    for claim in ("groups", "roles"):
        for role in userinfo.get(claim, []):
            if role in valid:
                return role
    return "reviewer"


@router.get("/oidc/authorize")
async def oidc_authorize():
    if not _oidc_configured():
        raise HTTPException(status_code=501, detail="OIDC integration not configured")

    import urllib.parse
    import urllib.request
    import json

    issuer = os.environ["OIDC_ISSUER_URL"].rstrip("/")
    discovery_url = f"{issuer}/.well-known/openid-configuration"

    try:
        with urllib.request.urlopen(discovery_url, timeout=10) as resp:
            config = json.loads(resp.read())
        auth_endpoint = config["authorization_endpoint"]
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to discover IdP endpoints")

    params = urllib.parse.urlencode({
        "client_id": os.environ["OIDC_CLIENT_ID"],
        "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
        "scope": "openid email profile",
        "response_type": "code",
    })

    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"{auth_endpoint}?{params}", status_code=307)


@router.post("/oidc/callback")
async def oidc_callback(
    body: OIDCCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    if not _oidc_configured():
        raise HTTPException(status_code=501, detail="OIDC integration not configured")

    import urllib.request
    import urllib.parse
    import json

    issuer = os.environ["OIDC_ISSUER_URL"].rstrip("/")

    # Discover endpoints
    try:
        with urllib.request.urlopen(f"{issuer}/.well-known/openid-configuration", timeout=10) as resp:
            config = json.loads(resp.read())
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to discover IdP endpoints")

    # Exchange code for tokens
    token_data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": body.code,
        "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
        "client_id": os.environ["OIDC_CLIENT_ID"],
        "client_secret": os.environ["OIDC_CLIENT_SECRET"],
    }).encode()

    try:
        req = urllib.request.Request(config["token_endpoint"], data=token_data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            tokens = json.loads(resp.read())
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token in IdP response")

    # Fetch userinfo
    try:
        req = urllib.request.Request(config["userinfo_endpoint"],
                                     headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            userinfo = json.loads(resp.read())
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from IdP")

    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="IdP did not return an email claim")

    role = _map_oidc_role(userinfo)

    # Create or update local user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(os.urandom(24).hex()),
            role=role,
        )
        db.add(user)
        await db.flush()
    else:
        user.role = role

    # Issue local JWT
    token, expires_at = create_access_token(user.id, user.email, user.role)
    session = Session(user_id=user.id, token_hash=_hash_token(token), expires_at=expires_at)
    db.add(session)

    await create_audit_event(
        db,
        package_id=None,
        actor_user_id=user.id,
        action="oidc_login",
        after_state={"email": email, "role": role, "idp": issuer},
    )
    await db.commit()

    return {"access_token": token, "token_type": "bearer",
            "user_id": user.id, "email": user.email, "role": user.role}

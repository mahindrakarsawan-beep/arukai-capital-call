"""Approvals router — admin approve/reject, audit log."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_role
from app.db import get_db
from app.models import Approval, AuditEvent, Package, User

router = APIRouter(tags=["approvals"])


class ApproveRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    note: Optional[str] = None


class ApprovalOut(BaseModel):
    id: str
    package_id: str
    decision: str
    note: Optional[str]
    decided_at: datetime
    decided_by: str

    model_config = {"from_attributes": True}


class AuditEventOut(BaseModel):
    id: str
    package_id: Optional[str]
    actor_user_id: Optional[str]
    action: str
    before_state: Optional[dict] = None
    after_state: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/packages/{pkg_id}/approve", response_model=ApprovalOut)
async def approve_package(
    pkg_id: str,
    body: ApproveRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin approves or rejects a package."""
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    result = await db.execute(select(Package).where(Package.id == pkg_id))
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")

    before_status = pkg.status
    pkg.status = body.decision
    pkg.updated_at = datetime.now(timezone.utc)

    approval = Approval(
        package_id=pkg.id,
        decided_by=current_user.id,
        decision=body.decision,
        note=body.note,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(approval)

    audit = AuditEvent(
        package_id=pkg.id,
        actor_user_id=current_user.id,
        action=f"{body.decision}_document",
        before_state={"status": before_status},
        after_state={"status": body.decision, "note": body.note},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(approval)

    return ApprovalOut(
        id=approval.id,
        package_id=approval.package_id,
        decision=approval.decision,
        note=approval.note,
        decided_at=approval.decided_at,
        decided_by=approval.decided_by,
    )


@router.get("/audit/{pkg_id}", response_model=list[AuditEventOut])
async def get_audit_log(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all audit events for a package."""
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.package_id == pkg_id)
        .order_by(AuditEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [
        AuditEventOut(
            id=e.id,
            package_id=e.package_id,
            actor_user_id=e.actor_user_id,
            action=e.action,
            before_state=e.before_state,
            after_state=e.after_state,
            created_at=e.created_at,
        )
        for e in events
    ]

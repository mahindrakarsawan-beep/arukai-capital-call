"""Global audit ledger router v0.2 (POR-147 / ARU-17-B1).

Endpoints:
  GET  /audit          — filtered, paginated global audit log (admin + approver only, S5)
  GET  /audit/export.csv — streaming CSV export (admin + approver only)
  GET  /audit/{pkg_id} — per-package audit trail (any authenticated)
"""
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_role
from app.db import get_db
from app.models import AuditEvent, User
from app.schemas import AuditEventOut

router = APIRouter(tags=["audit"])


class AuditPageOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditEventOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAX_DATE_RANGE_DAYS = 90


def _build_filters(
    actor_user_id: Optional[str],
    action: Optional[str],
    package_id: Optional[str],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
) -> list:
    """Build SQLAlchemy filter conditions."""
    conditions = []
    if actor_user_id:
        conditions.append(AuditEvent.actor_user_id == actor_user_id)
    if action:
        conditions.append(AuditEvent.action == action)
    if package_id:
        conditions.append(AuditEvent.package_id == package_id)
    if from_date:
        conditions.append(AuditEvent.created_at >= from_date)
    if to_date:
        conditions.append(AuditEvent.created_at <= to_date)
    return conditions


# ---------------------------------------------------------------------------
# POR-158 #7 — Hash-chain verification (admin only)
# ---------------------------------------------------------------------------


class AuditVerifyResponse(BaseModel):
    ok: bool
    total_events: int
    first_tampered_id: Optional[str] = None


@router.get("/audit/verify", response_model=AuditVerifyResponse)
async def verify_audit_chain(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Walk the audit_events hash chain and report the first tampered row.

    Any DBA-level mutation (UPDATE bypassing the append-only trigger, or a
    rewrite of payload fields) will produce a recomputed event_hash that
    diverges from the stored value, or a prev_hash that no longer matches
    the walking cursor. Either condition returns ok=false with the id of
    the first divergent row.
    """
    from app.audit_chain import verify_chain

    result = await verify_chain(db)
    return AuditVerifyResponse(**result)


# ---------------------------------------------------------------------------
# Global audit ledger (admin + approver only — S5)
# ---------------------------------------------------------------------------

@router.get("/audit", response_model=AuditPageOut)
async def list_audit_events(
    actor_user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    package_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None, description="ISO datetime for keyset pagination"),
    current_user: User = Depends(require_role("admin", "approver")),
    db: AsyncSession = Depends(get_db),
):
    """Global audit ledger. Role gate: admin or approver only (S5).
    Supports cursor-based pagination via created_at DESC.
    Date range capped at 90 days per request (R11).
    """
    # Validate date range cap
    if from_date and to_date:
        delta = to_date - from_date
        if delta.days > MAX_DATE_RANGE_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days",
            )

    conditions = _build_filters(actor_user_id, action, package_id, from_date, to_date)

    # Cursor pagination
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            conditions.append(AuditEvent.created_at < cursor_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor format")

    base_q = select(AuditEvent)
    if conditions:
        base_q = base_q.where(and_(*conditions))

    # Count (without cursor for total)
    from sqlalchemy import func
    count_conditions = _build_filters(actor_user_id, action, package_id, from_date, to_date)
    count_q = select(func.count(AuditEvent.id))
    if count_conditions:
        count_q = count_q.where(and_(*count_conditions))
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Fetch page
    q = base_q.order_by(AuditEvent.created_at.desc()).limit(limit)
    result = await db.execute(q)
    events = result.scalars().all()

    items = [AuditEventOut.model_validate(e) for e in events]

    return AuditPageOut(
        total=total,
        page=1,
        page_size=limit,
        items=items,
    )


# ---------------------------------------------------------------------------
# CSV export (admin + approver only)
# ---------------------------------------------------------------------------

@router.get("/audit/export.csv")
async def export_audit_csv(
    actor_user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    package_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: User = Depends(require_role("admin", "approver")),
    db: AsyncSession = Depends(get_db),
):
    """Streaming CSV export of audit events. Role gate: admin or approver."""
    conditions = _build_filters(actor_user_id, action, package_id, from_date, to_date)

    q = select(AuditEvent).order_by(AuditEvent.created_at.asc())
    if conditions:
        q = q.where(and_(*conditions))

    result = await db.execute(q)
    events = result.scalars().yield_per(500)

    def _generate_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        # Header
        writer.writerow([
            "id", "package_id", "actor_user_id", "action",
            "before_state", "after_state", "created_at",
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for e in events:
            writer.writerow([
                e.id,
                e.package_id or "",
                e.actor_user_id or "",
                e.action,
                str(e.before_state) if e.before_state else "",
                str(e.after_state) if e.after_state else "",
                e.created_at.isoformat(),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"audit-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        _generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Per-package audit trail (any authenticated user)
# ---------------------------------------------------------------------------

@router.get("/audit/{pkg_id}", response_model=list[AuditEventOut])
async def get_package_audit(
    pkg_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all audit events for a specific package."""
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.package_id == pkg_id)
        .order_by(AuditEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [AuditEventOut.model_validate(e) for e in events]

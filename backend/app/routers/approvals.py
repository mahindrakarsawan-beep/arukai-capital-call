"""Approvals router v0.2 — backward-compatible bridge.

The canonical attestation endpoint is now POST /packages/{id}/attest.
This file keeps the v0.1 POST /approvals/{pkg_id} endpoint alive but
returns 410 Gone with a pointer to the new endpoint.

The audit_router alias (GET /audit/{pkg_id}) is preserved for import
compatibility with main.py — it now delegates to the audit router.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# Keep audit_router as an empty alias; main.py imports it
audit_router = APIRouter(tags=["audit-legacy"])

router = APIRouter(prefix="/approvals", tags=["approvals-deprecated"])


class ApproveRequest(BaseModel):
    decision: str
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


@router.post("/{pkg_id}", status_code=410)
async def approve_package_deprecated(pkg_id: str, body: ApproveRequest):
    """Deprecated v0.1 endpoint. Use POST /packages/{id}/attest instead."""
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use POST /packages/{id}/attest instead.",
    )

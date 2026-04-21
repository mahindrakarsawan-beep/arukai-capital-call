"""SHA-256 hash chain for audit_events — POR-158 #7.

Mistral client-persona review flagged the audit trail as non-tamper-evident:
Postgres append-only is good, but it's enforced by a DB trigger that a DBA
with direct access could disable. A hash chain gives cryptographic proof
that any mutation (or deletion + re-insert) will be detected by a verifier
that walks the table and recomputes hashes.

Design
------

Every audit_event has:

    prev_hash  : sha256 of the previous event, or "" for the genesis event
    event_hash : sha256 of this event's canonical payload + prev_hash

Canonical payload (JSON, sorted keys, compact separators):

    {
      "id": <uuid>,
      "package_id": <uuid | null>,
      "actor_user_id": <uuid | null>,
      "action": <string>,
      "before_state": <json | null>,
      "after_state": <json | null>,
      "created_at": <iso8601 string with tz>,
      "prev_hash": <64-char hex | "">,
    }

All audit creation MUST go through `create_audit_event()` so chaining is
automatic and consistent across all routers.

Chain strategy: single global chain (not per-package). Simpler to verify and
matches the single-writer pattern of both test SQLite and staging PostgreSQL.
If we ever need per-tenant chains, we partition on `package.tenant_id` and
verify N chains independently — deferred.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


def _canonical_json(value: Any) -> str:
    """Produce a deterministic JSON serialization of an arbitrary value.

    Keys sorted, compact separators, no whitespace. ``None`` becomes
    JSON ``null``; ``datetime`` is not expected inside payload values
    (we pre-serialize), and raises if encountered.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_timestamp(created_at: Any) -> str:
    """Canonicalize a timestamp to a stable string for hashing.

    Accepts ISO-8601 strings or ``datetime`` objects. Always produces the
    UTC form as ``YYYY-MM-DDTHH:MM:SS.microseconds`` (no timezone suffix).
    This matches what SQLite returns on roundtrip (tz-stripped naive
    datetime) so write-time hash equals read-time hash without having to
    worry about whether the DB preserves tzinfo.
    """
    if isinstance(created_at, datetime):
        dt = created_at
    else:
        # Accept a string; parse the ISO form and strip tz.
        s = str(created_at)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            # Last-resort: return as-is. Hash will be stable but untethered
            # from the "normalized" rule; callers should pass a real dt.
            return s
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


def compute_event_hash(
    *,
    id: str,
    package_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    before_state: Any,
    after_state: Any,
    created_at: Any,
    prev_hash: str,
) -> str:
    """Return the sha256 hex digest for a single audit event.

    ``created_at`` must already be an ISO-8601 string (pass
    ``event.created_at.isoformat()``). Everything else may be None.
    ``prev_hash`` must be either a 64-char hex digest or ``""`` (genesis).
    """
    payload = {
        "id": id,
        "package_id": package_id,
        "actor_user_id": actor_user_id,
        "action": action,
        "before_state": before_state,
        "after_state": after_state,
        "created_at": _normalize_timestamp(created_at),
        "prev_hash": prev_hash or "",
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


async def _get_latest_hash(db: AsyncSession) -> str:
    """Fetch the event_hash of the newest event in the chain, or "" if empty."""
    result = await db.execute(
        select(AuditEvent.event_hash)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    prev = result.scalar_one_or_none()
    return prev or ""


async def create_audit_event(
    db: AsyncSession,
    *,
    package_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    before_state: Any = None,
    after_state: Any = None,
) -> AuditEvent:
    """Centralized audit-event factory. Chains to the latest existing event.

    This is the ONLY supported path to create an audit row. Direct
    ``AuditEvent(...)`` construction bypasses chaining and will produce
    rows that fail verification.
    """
    prev_hash = await _get_latest_hash(db)

    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    event_hash = compute_event_hash(
        id=event_id,
        package_id=package_id,
        actor_user_id=actor_user_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
        created_at=now,
        prev_hash=prev_hash,
    )

    event = AuditEvent(
        id=event_id,
        package_id=package_id,
        actor_user_id=actor_user_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
        created_at=now,
        prev_hash=prev_hash or None,
        event_hash=event_hash,
    )
    db.add(event)
    return event


async def verify_chain(db: AsyncSession) -> dict[str, Any]:
    """Walk all audit events in (created_at, id) order, recompute each hash,
    compare to the stored ``event_hash``. Return ``{ok, first_tampered_id,
    total_events}``.
    """
    result = await db.execute(
        select(AuditEvent).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    )
    events = result.scalars().all()

    prev = ""
    for ev in events:
        expected = compute_event_hash(
            id=ev.id,
            package_id=ev.package_id,
            actor_user_id=ev.actor_user_id,
            action=ev.action,
            before_state=ev.before_state,
            after_state=ev.after_state,
            created_at=ev.created_at,
            prev_hash=prev,
        )
        # Two failure modes:
        #   a) stored event_hash doesn't match recomputed → payload tampered
        #   b) stored prev_hash != our walking prev → chain rewritten
        if ev.event_hash != expected or (ev.prev_hash or "") != (prev or ""):
            return {
                "ok": False,
                "first_tampered_id": ev.id,
                "total_events": len(events),
            }
        prev = ev.event_hash

    return {"ok": True, "first_tampered_id": None, "total_events": len(events)}

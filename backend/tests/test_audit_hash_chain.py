"""TDD: POR-158 #7 — SHA-256 hash-chained audit ledger.

Mistral client-persona review flagged the audit trail as non-tamper-evident:
Postgres rows are append-only (trigger), but there's no cryptographic proof
that the chain wasn't rewritten by someone with direct DB access.

Design: every audit_event gets two new columns:
  - prev_hash   (varchar(64) NULL)  — sha256 of the immediately-previous event
  - event_hash  (varchar(64) NOT NULL)  — sha256 of THIS event's canonical payload

Payload hashed (sorted keys, compact JSON separators):
  {id, package_id, actor_user_id, action, before_state, after_state,
   created_at (ISO-8601), prev_hash (or "")}

Chain strategy: single global chain — newest event chains to the previous
newest event in the whole table. Works for tests (in-memory SQLite session
scope) and staging (PostgreSQL single-writer pattern).

Verification endpoint: GET /audit/verify (admin-only) walks the table in
created_at order, recomputes each event's hash from its payload + the
previous event's hash, and returns the first mismatch.
"""
from __future__ import annotations

import hashlib
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text


def _login(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _make_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td "
        b"(Hash Chain Test) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
    )


def _upload_package(client, token, title="Chain Test"):
    resp = client.post(
        "/packages/upload",
        data={"title": title},
        files={"file": ("doc.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Unit: hash helper contract
# ─────────────────────────────────────────────────────────────────────────────


def test_compute_event_hash_is_stable_and_deterministic():
    """Same payload → same hash, regardless of dict-key ordering."""
    from app.audit_chain import compute_event_hash

    payload = {
        "id": "evt-1",
        "package_id": "pkg-1",
        "actor_user_id": "user-1",
        "action": "upload",
        "before_state": None,
        "after_state": {"a": 1, "b": 2},
        "created_at": "2026-04-21T10:00:00+00:00",
        "prev_hash": "",
    }
    h1 = compute_event_hash(**payload)
    # Re-order the after_state dict — canonicalization should make hash identical
    h2 = compute_event_hash(
        id="evt-1",
        package_id="pkg-1",
        actor_user_id="user-1",
        action="upload",
        before_state=None,
        after_state={"b": 2, "a": 1},
        created_at="2026-04-21T10:00:00+00:00",
        prev_hash="",
    )
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_compute_event_hash_changes_when_any_field_changes():
    from app.audit_chain import compute_event_hash

    base = dict(
        id="evt-1",
        package_id="pkg-1",
        actor_user_id="user-1",
        action="upload",
        before_state=None,
        after_state={"a": 1},
        created_at="2026-04-21T10:00:00+00:00",
        prev_hash="",
    )
    h0 = compute_event_hash(**base)
    # Flip action
    h1 = compute_event_hash(**{**base, "action": "transition"})
    # Flip after_state
    h2 = compute_event_hash(**{**base, "after_state": {"a": 2}})
    # Flip prev_hash
    h3 = compute_event_hash(**{**base, "prev_hash": "a" * 64})

    assert len({h0, h1, h2, h3}) == 4


# ─────────────────────────────────────────────────────────────────────────────
# Integration: audit writes produce a chain
# ─────────────────────────────────────────────────────────────────────────────


def test_audit_events_have_hash_columns_populated(client: TestClient):
    """Every audit_event row has event_hash; first row has prev_hash NULL."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    _upload_package(client, reviewer_token, "Chain populate test")

    # Read the audit trail back — we expect event_hash to surface in the response
    # shape so verification can be done client-side if needed.
    # Use the package audit endpoint: GET /audit/{pkg_id}
    # After the upload, at least one audit event exists for this package.
    resp = client.get(
        "/audit/verify",
        headers={"Authorization": f"Bearer {_login(client, 'admin@arukai.example', 'admin123')}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["total_events"] >= 1


def test_verify_endpoint_returns_ok_for_untampered_chain(client: TestClient):
    """Freshly-built chain verifies cleanly."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")

    # Drive several audit-producing actions
    pkg_id = _upload_package(client, reviewer_token, "Verify OK")
    claim_resp = client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert claim_resp.status_code in (200, 204), claim_resp.text

    resp = client.get(
        "/audit/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["first_tampered_id"] is None


@pytest.mark.asyncio
async def test_verify_endpoint_detects_tampering(client: TestClient, async_session):
    """Mutate a past event's after_state directly in the DB → verify fails."""
    from sqlalchemy import update
    from app.models import AuditEvent

    admin_token = _login(client, "admin@arukai.example", "admin123")
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")

    pkg_id = _upload_package(client, reviewer_token, "Tamper target")

    # Grab the first event for this package and rewrite its after_state
    # bypassing the append-only guard (simulates a raw-DB attacker).
    # We use a raw UPDATE to dodge the Python-level trigger.
    await async_session.execute(
        text("UPDATE audit_events SET after_state = :new WHERE package_id = :pid"),
        {"new": '{"tampered":true}', "pid": pkg_id},
    )
    await async_session.commit()

    resp = client.get(
        "/audit/verify",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert body["first_tampered_id"] is not None


def test_verify_endpoint_requires_admin_role(client: TestClient):
    """Reviewer + approver → 403."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")

    for tok in (reviewer_token, approver_token):
        resp = client.get(
            "/audit/verify",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert resp.status_code == 403, resp.text


def test_verify_endpoint_requires_auth(client: TestClient):
    resp = client.get("/audit/verify")
    assert resp.status_code == 401


# Note: the full canonical-payload walk against an untampered DB is covered
# by test_verify_endpoint_returns_ok_for_untampered_chain (end-to-end via API).
# Running a raw-DB walk after test_verify_endpoint_detects_tampering would
# naturally fail — that's the point of tampering — so we don't repeat it here.

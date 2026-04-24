"""TDD: POR-160 flag-field endpoint — request human review on a low-confidence
extracted field. Pure audit-trail write (no state transition, no mutation).

Role gate: reviewer, approver, admin. Viewer/uploader must be 403.
"""
import io

import pytest
from fastapi.testclient import TestClient


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
        b"(Capital Call Notice Q2 2026) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
    )


def _upload_package(client, token, title="Flag Test"):
    pdf = io.BytesIO(_make_pdf_bytes())
    resp = client.post(
        "/packages/upload",
        data={"title": title},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()["id"]


def test_reviewer_can_flag_field(client: TestClient):
    """Reviewer POSTs /flag-field → 201 with package_id + field_name + audit id."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/flag-field",
        json={
            "field_name": "amount_due",
            "field_confidence": 0.42,
            "note": "Comma looks wrong",
        },
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["package_id"] == pkg_id
    assert data["field_name"] == "amount_due"
    assert data["audit_event_id"]
    assert data["requested_at"]
    assert data["requested_by"]


def test_approver_can_flag_field(client: TestClient):
    """Approver may also flag fields (broader role gate than reviewer-only)."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/flag-field",
        json={"field_name": "due_date"},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 201, resp.text


def test_admin_can_flag_field(client: TestClient):
    """Admin role also permitted."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/flag-field",
        json={"field_name": "fund_name"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201


def test_flag_requires_auth(client: TestClient):
    """Missing auth → 401."""
    resp = client.post(
        "/packages/some-id/flag-field",
        json={"field_name": "amount_due"},
    )
    assert resp.status_code == 401


def test_flag_rejects_empty_field_name(client: TestClient):
    """Empty/whitespace field_name → 400."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/flag-field",
        json={"field_name": "   "},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 400


def test_flag_unknown_package_returns_404(client: TestClient):
    """Nonexistent package_id → 404."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")

    resp = client.post(
        "/packages/nonexistent-pkg-id/flag-field",
        json={"field_name": "amount_due"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 404


def test_flag_writes_audit_event(client: TestClient):
    """The flag action surfaces in GET /packages/{id}/audit as action=field_review_requested."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token)

    flag_resp = client.post(
        f"/packages/{pkg_id}/flag-field",
        json={"field_name": "call_amount", "field_confidence": 0.35},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert flag_resp.status_code == 201

    audit_resp = client.get(
        f"/audit/{pkg_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    events = audit_resp.json()
    actions = [e["action"] for e in events]
    assert "field_review_requested" in actions, f"Got actions: {actions}"

    event = next(e for e in events if e["action"] == "field_review_requested")
    after = event["after_state"]
    assert after["field_name"] == "call_amount"
    assert after["field_confidence"] == 0.35


def test_flag_same_field_twice_writes_two_events(client: TestClient):
    """No server-side dedup — each click records a new audit event (signals, not state)."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token)

    for _ in range(2):
        resp = client.post(
            f"/packages/{pkg_id}/flag-field",
            json={"field_name": "amount_due"},
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 201

    audit_resp = client.get(
        f"/audit/{pkg_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    events = [e for e in audit_resp.json() if e["action"] == "field_review_requested"]
    assert len(events) == 2

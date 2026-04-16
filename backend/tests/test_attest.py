"""TDD: Attestation endpoint tests — atomic, state check, role gate.
(POR-147 / ARU-17-B1)
"""
import io
import pytest
from fastapi.testclient import TestClient


def _login(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
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


def _upload_package(client, token, title="Attest Test"):
    pdf = io.BytesIO(_make_pdf_bytes())
    resp = client.post(
        "/packages/upload",
        data={"title": title},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _route_to_approval(client, pkg_id, reviewer_token):
    """Move package through the states to routed_for_approval.

    Handles both intake_complete (high confidence) and exception_surfaced (no API key).
    """
    detail = client.get(
        f"/packages/{pkg_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    state = detail.json()["state"]

    if state == "exception_surfaced":
        # No API key — package went to exception_surfaced
        # Resolve exception as admin then continue
        admin_token_resp = client.post(
            "/auth/login", json={"email": "admin@arukai.example", "password": "admin123"}
        )
        admin_token = admin_token_resp.json()["access_token"]
        client.post(
            f"/packages/{pkg_id}/transition",
            json={"to_state": "intake_complete"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    # Claim
    client.post(f"/packages/{pkg_id}/claim", headers={"Authorization": f"Bearer {reviewer_token}"})
    # Route for approval
    resp = client.post(
        f"/packages/{pkg_id}/transition",
        json={"to_state": "routed_for_approval"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    return resp


def test_approver_can_approve(client: TestClient):
    """Approver can attest approval on a routed_for_approval package."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token, "Approve Test")

    route_resp = _route_to_approval(client, pkg_id, reviewer_token)
    assert route_resp.status_code == 200

    resp = client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "approved", "note": "All looks good."},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["decision"] == "approved"
    assert data["is_final"] is True


def test_approver_can_reject_with_note(client: TestClient):
    """Approver can record rejection with required note."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token, "Reject Test")

    _route_to_approval(client, pkg_id, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "rejected", "note": "Insufficient documentation."},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "rejected"


def test_rejection_requires_note(client: TestClient):
    """Rejection without note returns 422."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token, "Reject No Note Test")

    _route_to_approval(client, pkg_id, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "rejected", "note": None},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 422


def test_reviewer_cannot_attest(client: TestClient):
    """Reviewer role cannot attest — 403."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Reviewer Attest Gate")

    _route_to_approval(client, pkg_id, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "approved"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 403


def test_admin_cannot_attest(client: TestClient):
    """Admin (operator) cannot attest — 403. Attestation is approver-only."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, reviewer_token, "Admin Attest Gate")

    _route_to_approval(client, pkg_id, reviewer_token)

    resp = client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


def test_attest_wrong_state_returns_409(client: TestClient):
    """Attest on a package in under_review (not routed_for_approval) returns 409."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, reviewer_token, "Attest Wrong State Test")

    # Get current state — could be exception_surfaced or intake_complete
    detail = client.get(
        f"/packages/{pkg_id}",
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    state = detail.json()["state"]

    # Move to under_review (neither routed_for_approval nor exception_surfaced)
    if state == "exception_surfaced":
        client.post(
            f"/packages/{pkg_id}/transition",
            json={"to_state": "intake_complete"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    # Claim to get to under_review
    client.post(f"/packages/{pkg_id}/claim", headers={"Authorization": f"Bearer {reviewer_token}"})

    # Now package is under_review — attest should return 409
    resp = client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "approved"},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 409


def test_attest_requires_auth(client: TestClient):
    """Attest without token → 401."""
    resp = client.post("/packages/some-id/attest", json={"action": "approved"})
    assert resp.status_code == 401


def test_attest_produces_decision_recorded_state(client: TestClient):
    """After attestation, package state is decision_recorded."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token, "Post Attest State Test")

    _route_to_approval(client, pkg_id, reviewer_token)

    client.post(
        f"/packages/{pkg_id}/attest",
        json={"action": "approved", "note": "LGTM"},
        headers={"Authorization": f"Bearer {approver_token}"},
    )

    # Check package state
    detail_resp = client.get(
        f"/packages/{pkg_id}",
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["state"] == "decision_recorded"


def test_deprecated_approvals_endpoint_returns_410(client: TestClient):
    """POST /approvals/{id} returns 410 Gone pointing to /attest."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    resp = client.post(
        "/approvals/some-id",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 410

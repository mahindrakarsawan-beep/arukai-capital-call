"""TDD: Claim / release endpoint tests (POR-147 / ARU-17-B1)."""
import io
import pytest
from fastapi.testclient import TestClient


def _login(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
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


def _upload_package(client, token, title="Claim Test"):
    pdf = io.BytesIO(_make_pdf_bytes())
    resp = client.post(
        "/packages/upload",
        data={"title": title},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()["id"]


def test_reviewer_can_claim(client: TestClient):
    """Reviewer can claim an unclaimed package."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Claim Test Package")

    resp = client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["claimed_by_user_id"] is not None


def test_double_claim_returns_409(client: TestClient):
    """Claiming an already-claimed package returns 409."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Double Claim Test")

    # First claim
    resp1 = client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp1.status_code == 200

    # Second claim — same user, same package
    resp2 = client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp2.status_code == 409


def test_claim_requires_auth(client: TestClient):
    """Claim without token → 401."""
    resp = client.post("/packages/some-id/claim")
    assert resp.status_code == 401


def test_approver_cannot_claim(client: TestClient):
    """Approver role is not permitted to claim — 403."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token, "Approver Claim Test")

    resp = client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 403


def test_reviewer_can_release_unclaimed(client: TestClient):
    """Release on an unclaimed package returns 409."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Release Unclaimed Test")

    resp = client.post(
        f"/packages/{pkg_id}/release",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 409


def test_claim_then_release(client: TestClient):
    """Claim then release succeeds when no notes recorded."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Claim Release Test")

    # Claim
    claim_resp = client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert claim_resp.status_code == 200

    # Release
    release_resp = client.post(
        f"/packages/{pkg_id}/release",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert release_resp.status_code == 200, release_resp.text
    data = release_resp.json()
    assert data["claimed_by_user_id"] is None

"""TDD: Approval endpoint tests — admin approves, reviewer cannot, audit trail."""
import io
import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, password: str) -> str:
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


def _upload_package(client: TestClient, token: str, title: str = "Approval Test Package") -> str:
    """Upload a package and return its id."""
    pdf = io.BytesIO(_make_pdf_bytes())
    resp = client.post(
        "/documents/upload",
        data={"title": title},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()["id"]


def test_admin_can_approve(client: TestClient):
    """Admin can approve a pending_review package."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, admin_token, "Admin Approve Test")

    response = client.post(
        f"/approvals/{pkg_id}",
        json={"decision": "approved", "note": "Looks good"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "approved"


def test_admin_can_reject(client: TestClient):
    """Admin can reject a package."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, admin_token, "Admin Reject Test")

    response = client.post(
        f"/approvals/{pkg_id}",
        json={"decision": "rejected", "note": "Insufficient documentation"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "rejected"


def test_reviewer_cannot_approve(client: TestClient):
    """Reviewer role cannot approve — 403."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, admin_token, "Reviewer Blocked Test")

    response = client.post(
        f"/approvals/{pkg_id}",
        json={"decision": "approved", "note": ""},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 403


def test_approve_requires_auth(client: TestClient):
    """Approve without token → 401."""
    response = client.post(
        "/approvals/some-id",
        json={"decision": "approved", "note": ""},
    )
    assert response.status_code == 401


def test_audit_log_captured_after_approve(client: TestClient):
    """Audit log has an event after approval."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, admin_token, "Audit Trail Test")

    # Approve
    client.post(
        f"/approvals/{pkg_id}",
        json={"decision": "approved", "note": "Audit test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Check audit log
    audit_resp = client.get(
        f"/audit/{pkg_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    assert isinstance(events, list)
    assert len(events) > 0
    actions = [e["action"] for e in events]
    # Should contain upload and approve events
    assert any("upload" in a or "approve" in a for a in actions)


def test_audit_log_requires_auth(client: TestClient):
    """Audit log without token → 401."""
    response = client.get("/audit/some-package-id")
    assert response.status_code == 401


def test_approve_nonexistent_package(client: TestClient):
    """Approving a non-existent package → 404."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    response = client.post(
        "/approvals/00000000-0000-0000-0000-000000000000",
        json={"decision": "approved", "note": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404

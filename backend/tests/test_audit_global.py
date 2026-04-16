"""TDD: Global audit ledger tests — filters, pagination, role gate.
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


def _upload_package(client, token, title="Audit Test"):
    pdf = io.BytesIO(_make_pdf_bytes())
    resp = client.post(
        "/packages/upload",
        data={"title": title},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_admin_can_access_global_audit(client: TestClient):
    """Admin can access the global audit ledger."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    resp = client.get("/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_approver_can_access_global_audit(client: TestClient):
    """Approver can access the global audit ledger (S5)."""
    approver_token = _login(client, "approver@arukai.example", "approver123")
    resp = client.get("/audit", headers={"Authorization": f"Bearer {approver_token}"})
    assert resp.status_code == 200


def test_reviewer_cannot_access_global_audit(client: TestClient):
    """Reviewer role is denied global audit ledger (S5) — 403."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    resp = client.get("/audit", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert resp.status_code == 403


def test_global_audit_requires_auth(client: TestClient):
    """Global audit without token → 401."""
    resp = client.get("/audit")
    assert resp.status_code == 401


def test_global_audit_filter_by_action(client: TestClient):
    """Filter by action returns only matching events."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    _upload_package(client, admin_token, "Audit Filter Test")

    resp = client.get(
        "/audit?action=upload_document",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["action"] == "upload_document"


def test_global_audit_filter_by_package_id(client: TestClient):
    """Filter by package_id returns only events for that package."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    pkg_id = _upload_package(client, admin_token, "Package Filter Audit Test")

    resp = client.get(
        f"/audit?package_id={pkg_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["package_id"] == pkg_id


def test_global_audit_pagination(client: TestClient):
    """Pagination: limit=1 returns only 1 item."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    # Upload to ensure there are events
    _upload_package(client, admin_token, "Pagination Test Package")

    resp = client.get(
        "/audit?limit=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 1


def test_global_audit_date_range_too_large(client: TestClient):
    """Date range > 90 days returns 400."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    resp = client.get(
        "/audit?from_date=2020-01-01T00:00:00&to_date=2026-01-01T00:00:00",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_csv_export_accessible_by_admin(client: TestClient):
    """Admin can download CSV export."""
    admin_token = _login(client, "admin@arukai.example", "admin123")
    resp = client.get(
        "/audit/export.csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


def test_csv_export_blocked_for_reviewer(client: TestClient):
    """Reviewer cannot download CSV export — 403."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    resp = client.get(
        "/audit/export.csv",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 403


def test_per_package_audit_accessible_to_reviewer(client: TestClient):
    """Per-package audit trail is accessible to any authenticated user."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Per Package Audit Test")

    resp = client.get(
        f"/audit/{pkg_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)
    assert len(events) > 0

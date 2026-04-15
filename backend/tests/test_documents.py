"""TDD: Document endpoint tests — upload, list, get, download, auth checks."""
import io
import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _make_pdf_bytes() -> bytes:
    """Minimal valid-ish PDF bytes with text layer."""
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


def test_upload_requires_auth(client: TestClient):
    """Upload without token → 401."""
    pdf = io.BytesIO(_make_pdf_bytes())
    response = client.post(
        "/documents/upload",
        data={"title": "Test Package"},
        files={"file": ("test.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 401


def test_upload_with_reviewer_token(client: TestClient):
    """Reviewer can upload a document."""
    token = _login(client, "reviewer@arukai.example", "reviewer123")
    pdf = io.BytesIO(_make_pdf_bytes())
    response = client.post(
        "/documents/upload",
        data={"title": "Q2 Capital Call"},
        files={"file": ("capital_call.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["title"] == "Q2 Capital Call"
    assert data["status"] in ("pending_classification", "pending_review")


def test_upload_with_admin_token(client: TestClient):
    """Admin can also upload."""
    token = _login(client, "admin@arukai.example", "admin123")
    pdf = io.BytesIO(_make_pdf_bytes())
    response = client.post(
        "/documents/upload",
        data={"title": "Admin Upload Test"},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


def test_list_packages_requires_auth(client: TestClient):
    """List without token → 401."""
    response = client.get("/documents")
    assert response.status_code == 401


def test_list_packages_returns_list(client: TestClient):
    """Authenticated user gets a list of packages."""
    token = _login(client, "admin@arukai.example", "admin123")
    response = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_package_detail(client: TestClient):
    """Get single package with classification."""
    token = _login(client, "admin@arukai.example", "admin123")
    # Upload first
    pdf = io.BytesIO(_make_pdf_bytes())
    upload = client.post(
        "/documents/upload",
        data={"title": "Detail Test"},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    pkg_id = upload.json()["id"]

    # Get detail
    response = client.get(f"/documents/{pkg_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pkg_id
    assert "documents" in data


def test_get_package_not_found(client: TestClient):
    """Non-existent package → 404."""
    token = _login(client, "admin@arukai.example", "admin123")
    response = client.get(
        "/documents/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_download_pdf(client: TestClient):
    """Download raw PDF bytes."""
    token = _login(client, "reviewer@arukai.example", "reviewer123")
    pdf_bytes = _make_pdf_bytes()
    pdf = io.BytesIO(pdf_bytes)
    upload = client.post(
        "/documents/upload",
        data={"title": "Download Test"},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    pkg_id = upload.json()["id"]

    # Download
    dl = client.get(
        f"/documents/{pkg_id}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/pdf")


def test_download_requires_auth(client: TestClient):
    """Download without token → 401."""
    response = client.get("/documents/some-id/pdf")
    assert response.status_code == 401

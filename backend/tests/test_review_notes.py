"""TDD: Reviewer notes tests — append-only, supersession chain, role gate.
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


def _upload_package(client, token, title="Note Test"):
    pdf = io.BytesIO(_make_pdf_bytes())
    resp = client.post(
        "/packages/upload",
        data={"title": title},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    return resp.json()["id"]


def test_reviewer_can_add_note(client: TestClient):
    """Reviewer can add a note to a package."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Note Creation Test")

    resp = client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "Fund name looks off — needs verification."},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["body"] == "Fund name looks off — needs verification."
    assert data["package_id"] == pkg_id


def test_approver_cannot_add_note(client: TestClient):
    """Approver role is not permitted to create review notes — 403 (R6)."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    approver_token = _login(client, "approver@arukai.example", "approver123")
    pkg_id = _upload_package(client, reviewer_token, "Approver Note Gate Test")

    resp = client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "This should not be allowed."},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 403


def test_note_requires_auth(client: TestClient):
    """Add note without token → 401."""
    resp = client.post(
        "/packages/some-id/review-notes",
        json={"body": "No auth"},
    )
    assert resp.status_code == 401


def test_empty_note_rejected(client: TestClient):
    """Empty note body must be rejected with 422."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Empty Note Test")

    resp = client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "   "},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 422


def test_notes_are_listed_newest_first(client: TestClient):
    """GET /review-notes returns notes newest first."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Note List Test")

    client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "First note"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "Second note"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    resp = client.get(
        f"/packages/{pkg_id}/review-notes",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 200
    notes = resp.json()
    assert len(notes) >= 2
    # Newest first — second note should come before first
    bodies = [n["body"] for n in notes]
    assert bodies.index("Second note") < bodies.index("First note")


def test_supersession_chain(client: TestClient):
    """Supersedes note creates a correction chain (R5)."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Supersession Test")

    # First note
    resp1 = client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "Original note with typo"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp1.status_code == 201
    note1_id = resp1.json()["id"]

    # Correction (supersedes first note)
    resp2 = client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "Corrected note", "supersedes_note_id": note1_id},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["supersedes_note_id"] == note1_id

    # Original note still exists (append-only — R5)
    resp_list = client.get(
        f"/packages/{pkg_id}/review-notes",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert len(resp_list.json()) >= 2


def test_supersedes_invalid_note_id(client: TestClient):
    """Superseding a non-existent note ID returns 404."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Bad Supersedes Test")

    resp = client.post(
        f"/packages/{pkg_id}/review-notes",
        json={
            "body": "Correction",
            "supersedes_note_id": "00000000-0000-0000-0000-000000000000",
        },
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 404


def test_release_claim_blocked_after_note(client: TestClient):
    """Reviewer cannot release claim after adding a note (R4)."""
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    pkg_id = _upload_package(client, reviewer_token, "Release After Note Test")

    # Claim first
    client.post(
        f"/packages/{pkg_id}/claim",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    # Add note
    client.post(
        f"/packages/{pkg_id}/review-notes",
        json={"body": "Cannot release after this"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    # Attempt release — should fail
    resp = client.post(
        f"/packages/{pkg_id}/release",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 409
    assert "cannot release claim after annotation" in resp.json()["detail"].lower()

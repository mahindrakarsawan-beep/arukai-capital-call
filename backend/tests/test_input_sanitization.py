# ---------------------------------------------------------------------------
# POR-158 #8 A1.1 audit findings (2026-04-21)
#
# Filename surfaces where UploadFile.filename flows today (no normalization):
#   * backend/app/routers/packages.py upload_package (~L403-L453):
#       - validate_pdf(raw, file.filename) — filename only logged on JS-reject,
#         never rejected on content
#       - Document(filename=file.filename or "upload.pdf") — stored verbatim
#       - _write_audit after_state={"filename": doc.filename, ...} — raw in
#         hash-chained audit row (GET /audit/{pkg_id})
#       - classify_document_text(filename=doc.filename) -> prompt-injection
#         surface: classify.py L240 interpolates "Document filename: {filename}"
#         directly into the LLM user message (and into _heuristic_type L124)
#       - returned in PackageOut / PackageDetailOut / PackageListOut + download
#         Content-Disposition header (L704) — CRLF/header-smuggling surface
#   * No central sanitize helper exists; no basename(), no null-byte strip,
#     no path-separator strip. Any fix in Task 2 must land once and be called
#     at the upload boundary before Document() + audit + classify.
#
# Test shape note: PackageDetailOut has NO top-level "filename" — the plan's
# stub used detail["filename"] which only exists on PackageListOut. Corrected
# to detail["documents"][0]["filename"] (per DocumentOut schema L61-L69).
# Audit endpoint confirmed at GET /audit/{pkg_id} (audit.py L222).
# ---------------------------------------------------------------------------
"""POR-158 #8 — upload with hostile filenames never leaks past the API surface.

Each hostile filename must:
  1. upload cleanly (201) — we don't 400 on the input; storage is inert
  2. appear in the GET /packages/{id} response as an *escaped* representation
     (no raw shell metacharacters, no path traversal segments)
  3. appear in the audit event's after_state sanitized the same way
"""
import io
import pytest
from fastapi.testclient import TestClient


HOSTILE_FILENAMES = [
    "../../../etc/passwd.pdf",
    "$(rm -rf /).pdf",
    "<script>alert(1)</script>.pdf",
    "file; DROP TABLE packages;--.pdf",
    "file\x00injection.pdf",
]


def _login(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<</Size 1/Root 1 0 R>>\n"
        b"startxref\n9\n%%EOF\n"
    )


@pytest.mark.parametrize("hostile", HOSTILE_FILENAMES)
def test_hostile_filename_is_sanitized_everywhere(client: TestClient, hostile: str):
    reviewer_token = _login(client, "reviewer@arukai.example", "reviewer123")
    resp = client.post(
        "/packages/upload",
        data={"title": f"Sanitize test: {hostile}"},
        files={"file": (hostile, io.BytesIO(_pdf_bytes()), "application/pdf")},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 201, resp.text
    pkg_id = resp.json()["id"]

    # Detail response: filename must be stored but stripped of path separators.
    # PackageDetailOut surfaces filenames on each DocumentOut in `documents[]`;
    # there is no top-level `filename` on the detail payload.
    detail = client.get(
        f"/packages/{pkg_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    ).json()
    assert detail["documents"], f"detail missing documents: {detail!r}"
    stored = detail["documents"][0]["filename"]
    assert ".." not in stored, f"path traversal leaked into detail: {stored!r}"
    assert "/" not in stored and "\\" not in stored
    assert "\x00" not in stored, "null byte must be stripped"

    # Audit: after_state JSON must not contain raw shell metacharacters
    admin_token = _login(client, "admin@arukai.example", "admin123")
    audit = client.get(
        f"/audit/{pkg_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    for ev in audit:
        after = str(ev.get("after_state") or "")
        assert "$(rm" not in after
        assert "DROP TABLE" not in after
        assert "<script>" not in after

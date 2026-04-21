# POR-158 #8 A1.1 audit findings → plan doc §A1.1
# Schema note: PackageDetailOut has no top-level "filename"; filenames live
# under detail["documents"][i]["filename"]. Audit endpoint is GET /audit/{pkg_id}.
# Null-byte case passes because Starlette's multipart parser strips it upstream.
"""POR-158 #8 — upload with hostile filenames never leaks past the API surface.

Each hostile filename must:
  1. upload cleanly (201) — we don't 400 on the input; storage is inert
  2. appear in the GET /packages/{id} response as a sanitized filename —
     stripped of path separators, null bytes, traversal segments, and CRLF
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
    "file\r\nContent-Disposition: attachment\r\n.pdf",
    "..\\..\\..\\windows\\system32\\evil.pdf",
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
        data={"title": "Sanitize test"},
        files={"file": (hostile, io.BytesIO(_pdf_bytes()), "application/pdf")},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == 201, resp.text
    pkg_id = resp.json()["id"]

    # Detail response: filename must be stored but stripped of path separators.
    # PackageDetailOut surfaces filenames on each DocumentOut in `documents[]`;
    # there is no top-level `filename` on the detail payload.
    detail_resp = client.get(
        f"/packages/{pkg_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["documents"], f"detail missing documents: {detail!r}"
    stored = detail["documents"][0]["filename"]
    assert ".." not in stored, f"path traversal leaked into detail: {stored!r}"
    assert "/" not in stored and "\\" not in stored
    assert "\x00" not in stored, "null byte must be stripped"
    assert stored, "filename must not be empty after sanitization"
    assert stored.endswith(".pdf"), f"extension must survive: {stored!r}"
    assert "\r" not in stored and "\n" not in stored, f"CRLF in stored: {stored!r}"

    # Audit: the filename field specifically must be sanitized. Other fields
    # (title, state) are constants and don't carry the hostile payload, so we
    # avoid a dict-wide substring scan that would false-positive on a legit
    # package title mentioning "DROP TABLE" etc.
    admin_token = _login(client, "admin@arukai.example", "admin123")
    audit_resp = client.get(
        f"/audit/{pkg_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audit_resp.status_code == 200, audit_resp.text
    audit = audit_resp.json()
    for ev in audit:
        after = ev.get("after_state") or {}
        # API may return JSON string or already-parsed dict depending on serializer
        if isinstance(after, str):
            import json as _json
            after = _json.loads(after)
        fn = str(after.get("filename") or "")
        assert ".." not in fn, f"path traversal in audit filename: {fn!r}"
        assert "/" not in fn and "\\" not in fn
        assert "\x00" not in fn
        assert "$(rm" not in fn
        assert "DROP TABLE" not in fn
        assert "<script>" not in fn
        assert "\r" not in fn and "\n" not in fn, f"CRLF in audit filename: {fn!r}"

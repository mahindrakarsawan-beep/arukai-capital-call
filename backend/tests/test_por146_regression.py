"""
POR-146 Regression Test Suite — Z1 (Miller gate).

Verifies none of the original 8 bugs can recur:

 1. Frontend fetch doesn't hit localhost (NEXT_PUBLIC_API_URL baked in build).
 2. /documents routes work (legacy bridge).
 3. CORS preflight passes from frontend origin.
 4. Upload endpoint accepts multipart POST.
 5. Approvals endpoint returns 410 Gone (deprecation bridge).
 6. Error responses don't crash React (pydantic detail array is string-friendly).
 7. Upload sends title field (title form field required on /documents/upload).
 8. Haiku model ID is correct (claude-haiku-4-5-20251001).

Each test is labelled BUG-{n} to match the incident log.
"""
import io
import re
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _login(client: TestClient, email: str, password: str) -> str:
    """Return JWT access token."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _make_minimal_pdf() -> bytes:
    """Return a well-formed minimal PDF that pypdf can parse."""
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


# ---------------------------------------------------------------------------
# BUG-1: Frontend fetch must not hard-code localhost
# ---------------------------------------------------------------------------

class TestBug1LocalhostNotBaked:
    """
    BUG-1: Fetch was hard-coded to localhost:8000 in production builds.
    Fix: all API calls in api.ts use NEXT_PUBLIC_API_URL env var.
    Regression guard: api.ts must not contain 'fetch("http://localhost' or
    the fallback localhost must only appear as the ?? default, never as a
    hard-coded string in a fetch() call.
    """

    API_TS = Path("/home/sawan/arukai-capital-call/frontend/src/lib/api.ts")

    def test_api_ts_exists(self):
        assert self.API_TS.exists(), f"api.ts not found at {self.API_TS}"

    def test_no_hardcoded_localhost_in_fetch_calls(self):
        """No fetch() call should directly embed 'localhost'."""
        src = self.API_TS.read_text()
        # Detect lines that have fetch( with a hard-coded localhost URL
        hardcoded = re.findall(
            r'fetch\(["\']http://localhost',
            src,
        )
        assert not hardcoded, (
            f"BUG-1 REGRESSION: Found hard-coded localhost in fetch() call(s) in api.ts: {hardcoded}"
        )

    def test_api_base_uses_env_var(self):
        """API_BASE must be derived from NEXT_PUBLIC_API_URL."""
        src = self.API_TS.read_text()
        assert "NEXT_PUBLIC_API_URL" in src, (
            "BUG-1 REGRESSION: NEXT_PUBLIC_API_URL not referenced in api.ts"
        )

    def test_no_hardcoded_localhost_in_upload_page(self):
        """Upload page also had a direct localhost reference in v0.1."""
        upload_page = Path(
            "/home/sawan/arukai-capital-call/frontend/src/app/documents/upload/page.tsx"
        )
        if not upload_page.exists():
            pytest.skip("Upload page not found")
        src = upload_page.read_text()
        # Any fetch( with literal localhost is a bug (env-var fallback inside ?? is OK)
        hardcoded = re.findall(r'fetch\(["\']http://localhost', src)
        assert not hardcoded, (
            f"BUG-1 REGRESSION: Hard-coded localhost in fetch() in upload/page.tsx: {hardcoded}"
        )


# ---------------------------------------------------------------------------
# BUG-2: /documents routes must work (legacy bridge)
# ---------------------------------------------------------------------------

class TestBug2DocumentsLegacyBridge:
    """
    BUG-2: POST /documents/upload and GET /documents returned 404 after the
    routes were renamed to /packages. Legacy bridge must keep them alive.
    """

    def test_documents_list_returns_200_or_401(self, client: TestClient):
        """GET /documents without auth → 401 (route exists)."""
        resp = client.get("/documents")
        # 401 = route exists but requires auth; 404 = bridge broken
        assert resp.status_code == 401, (
            f"BUG-2 REGRESSION: GET /documents returned {resp.status_code}, expected 401. "
            "Legacy bridge may be broken."
        )

    def test_documents_upload_route_exists(self, client: TestClient):
        """POST /documents/upload without auth → 401/422, NOT 404/405."""
        resp = client.post("/documents/upload")
        assert resp.status_code in (401, 422), (
            f"BUG-2 REGRESSION: POST /documents/upload returned {resp.status_code}. "
            "Expected 401 (no auth) or 422 (missing body). Legacy bridge may be broken."
        )

    def test_documents_get_detail_route_exists(self, client: TestClient):
        """GET /documents/{id} without auth → 401, NOT 404."""
        resp = client.get("/documents/nonexistent-id-for-route-check")
        assert resp.status_code == 401, (
            f"BUG-2 REGRESSION: GET /documents/{{id}} returned {resp.status_code}, expected 401. "
            "Legacy bridge may be broken."
        )

    def test_documents_upload_succeeds_with_auth(self, client: TestClient):
        """POST /documents/upload with valid auth and PDF → 201."""
        token = _login(client, "admin@arukai.example", "admin123")
        pdf = io.BytesIO(_make_minimal_pdf())
        resp = client.post(
            "/documents/upload",
            data={"title": "BUG-2 Legacy Bridge Test"},
            files={"file": ("bug2.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, (
            f"BUG-2 REGRESSION: POST /documents/upload returned {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# BUG-3: CORS preflight from frontend origin must pass
# ---------------------------------------------------------------------------

class TestBug3CorsPreflightPasses:
    """
    BUG-3: CORS middleware was not configured, causing preflight OPTIONS
    requests from the frontend origin to fail with 400/404.
    Fix: CORSMiddleware added in main.py with frontend origins allowed.
    """

    FRONTEND_ORIGINS = [
        "http://localhost:3000",
        "https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app",
    ]

    def test_cors_preflight_localhost(self, client: TestClient):
        """OPTIONS preflight from localhost:3000 → 200 with CORS headers."""
        resp = client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        assert resp.status_code == 200, (
            f"BUG-3 REGRESSION: CORS preflight from localhost:3000 returned {resp.status_code}. "
            "CORSMiddleware may be broken."
        )
        # FastAPI CORSMiddleware sets these headers on preflight
        assert "access-control-allow-origin" in resp.headers, (
            "BUG-3 REGRESSION: 'access-control-allow-origin' header missing from preflight response."
        )

    def test_cors_preflight_staging_origin(self, client: TestClient):
        """OPTIONS preflight from staging frontend origin → 200 with CORS headers."""
        staging_origin = (
            "https://arukai-capital-call-frontend-staging-1035777337524.europe-west4.run.app"
        )
        resp = client.options(
            "/auth/login",
            headers={
                "Origin": staging_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        assert resp.status_code == 200, (
            f"BUG-3 REGRESSION: CORS preflight from staging origin returned {resp.status_code}."
        )
        assert "access-control-allow-origin" in resp.headers, (
            "BUG-3 REGRESSION: 'access-control-allow-origin' missing from staging CORS preflight."
        )

    def test_cors_disallows_arbitrary_origin(self, client: TestClient):
        """OPTIONS preflight from an arbitrary unknown origin should not be allowed."""
        resp = client.options(
            "/auth/login",
            headers={
                "Origin": "https://evil.attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        # Should either return 400 or not include the attacker origin in the allow header
        if "access-control-allow-origin" in resp.headers:
            assert resp.headers["access-control-allow-origin"] != "https://evil.attacker.example", (
                "BUG-3 REGRESSION: CORS allows arbitrary origins — misconfigured wildcard?"
            )


# ---------------------------------------------------------------------------
# BUG-4: Upload endpoint accepts multipart POST
# ---------------------------------------------------------------------------

class TestBug4UploadAcceptsMultipart:
    """
    BUG-4: The upload endpoint rejected multipart/form-data POSTs in v0.1
    because the route was defined with JSON body instead of Form+File.
    Fix: route uses `title: str = Form(...)` and `file: UploadFile`.
    """

    def test_upload_accepts_multipart_with_title_and_file(self, client: TestClient):
        """POST /packages/upload with multipart form → 201."""
        token = _login(client, "admin@arukai.example", "admin123")
        pdf = io.BytesIO(_make_minimal_pdf())
        resp = client.post(
            "/packages/upload",
            data={"title": "BUG-4 Multipart Test"},
            files={"file": ("multipart.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, (
            f"BUG-4 REGRESSION: Multipart POST /packages/upload failed with {resp.status_code}: "
            f"{resp.text}"
        )
        body = resp.json()
        assert "id" in body, "BUG-4 REGRESSION: Response missing 'id' field."
        assert body["title"] == "BUG-4 Multipart Test", (
            f"BUG-4 REGRESSION: 'title' not echoed correctly: {body.get('title')}"
        )

    def test_upload_rejects_json_body(self, client: TestClient):
        """POST /packages/upload with JSON body (not multipart) → 422."""
        token = _login(client, "admin@arukai.example", "admin123")
        resp = client.post(
            "/packages/upload",
            json={"title": "Should Fail"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422, (
            f"BUG-4 REGRESSION: JSON body to /packages/upload returned {resp.status_code}, "
            "expected 422 (only multipart accepted)."
        )

    def test_upload_rejects_empty_file(self, client: TestClient):
        """POST /packages/upload with empty file → 400."""
        token = _login(client, "admin@arukai.example", "admin123")
        resp = client.post(
            "/packages/upload",
            data={"title": "Empty File Test"},
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400, (
            f"BUG-4 REGRESSION: Empty file should return 400, got {resp.status_code}."
        )


# ---------------------------------------------------------------------------
# BUG-5: POST /approvals/{id} returns 410 Gone (deprecation bridge)
# ---------------------------------------------------------------------------

class TestBug5ApprovalsDeprecation410:
    """
    BUG-5: POST /approvals/{id} was silently dropping requests. It now
    returns 410 Gone to tell callers to migrate to POST /packages/{id}/attest.
    """

    def test_approvals_endpoint_returns_410(self, client: TestClient):
        """POST /approvals/{id} → 410 Gone regardless of auth."""
        resp = client.post("/approvals/any-package-id", json={"decision": "approved"})
        assert resp.status_code == 410, (
            f"BUG-5 REGRESSION: POST /approvals/{{id}} returned {resp.status_code}, expected 410."
        )

    def test_approvals_410_detail_mentions_migration_path(self, client: TestClient):
        """410 response body must tell callers where to migrate."""
        resp = client.post("/approvals/any-package-id", json={})
        body = resp.json()
        detail = body.get("detail", "")
        assert "attest" in detail.lower() or "/packages/" in detail, (
            f"BUG-5 REGRESSION: 410 detail doesn't mention migration path: {detail!r}"
        )

    def test_approvals_410_with_auth(self, client: TestClient):
        """410 is returned even for authenticated requests — not an auth issue."""
        token = _login(client, "approver@arukai.example", "approver123")
        resp = client.post(
            "/approvals/any-package-id",
            json={"decision": "approved"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 410, (
            f"BUG-5 REGRESSION: Authenticated POST /approvals/{{id}} returned {resp.status_code}, "
            "expected 410."
        )


# ---------------------------------------------------------------------------
# BUG-6: Error responses don't crash React (pydantic detail array)
# ---------------------------------------------------------------------------

class TestBug6ErrorResponsesAreReactSafe:
    """
    BUG-6: Pydantic validation errors return `detail` as an array of objects
    like [{"loc": ..., "msg": ..., "type": ...}]. The React error handler in
    api.ts was calling `body.detail.toString()` which returned "[object Object]"
    or crashed on non-string detail.
    Fix: handleResponse() in api.ts checks `typeof raw === 'string'` and
    `Array.isArray(raw)` before displaying.

    Backend side: we verify that validation errors DO return pydantic arrays
    so the frontend guard has something to protect against.
    """

    def test_missing_required_field_returns_pydantic_array_detail(self, client: TestClient):
        """POST /auth/login with missing password → 422 with array detail."""
        resp = client.post("/auth/login", json={"email": "x@x.com"})  # no password
        assert resp.status_code == 422, (
            f"BUG-6 REGRESSION: Login without password returned {resp.status_code}, expected 422."
        )
        body = resp.json()
        # Pydantic v2 puts validation errors in "detail" as an array
        detail = body.get("detail")
        assert isinstance(detail, list), (
            f"BUG-6 REGRESSION: detail is not a list (got {type(detail).__name__}). "
            "Frontend guard won't work."
        )
        # Each item must have a 'msg' key for the frontend to extract
        for item in detail:
            assert "msg" in item, (
                f"BUG-6 REGRESSION: Pydantic error item missing 'msg' key: {item}"
            )

    def test_api_ts_handles_array_detail(self):
        """api.ts handleResponse must have Array.isArray guard."""
        api_ts = Path("/home/sawan/arukai-capital-call/frontend/src/lib/api.ts")
        src = api_ts.read_text()
        assert "Array.isArray" in src, (
            "BUG-6 REGRESSION: api.ts handleResponse does not have Array.isArray guard. "
            "Pydantic array details will crash or display '[object Object]'."
        )

    def test_non_existent_package_returns_string_detail(self, client: TestClient):
        """GET /packages/{id} for missing ID → 404 with string detail."""
        token = _login(client, "admin@arukai.example", "admin123")
        resp = client.get(
            "/packages/nonexistent-id-zzzz",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        body = resp.json()
        detail = body.get("detail")
        assert isinstance(detail, str), (
            f"BUG-6 REGRESSION: 404 detail should be a string, got {type(detail).__name__}: {detail}"
        )


# ---------------------------------------------------------------------------
# BUG-7: Upload sends title field (required by backend)
# ---------------------------------------------------------------------------

class TestBug7UploadSendsTitleField:
    """
    BUG-7: The v0.1 upload page did not append 'title' to FormData, causing
    422 from the backend (title: str = Form(...) is required).
    Fix: upload/page.tsx appends `form.append("title", title)`.
    """

    def test_upload_without_title_returns_422(self, client: TestClient):
        """POST /documents/upload without title → 422 (title is required)."""
        token = _login(client, "admin@arukai.example", "admin123")
        pdf = io.BytesIO(_make_minimal_pdf())
        # Do NOT send title field
        resp = client.post(
            "/documents/upload",
            files={"file": ("no_title.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422, (
            f"BUG-7 REGRESSION: Upload without title returned {resp.status_code}, expected 422. "
            "If this passes, the title field may no longer be required — check the route."
        )

    def test_upload_with_title_returns_201(self, client: TestClient):
        """POST /documents/upload WITH title → 201 (title correctly handled)."""
        token = _login(client, "admin@arukai.example", "admin123")
        pdf = io.BytesIO(_make_minimal_pdf())
        resp = client.post(
            "/documents/upload",
            data={"title": "BUG-7 Title Field Test"},
            files={"file": ("with_title.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, (
            f"BUG-7 REGRESSION: Upload with title returned {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body.get("title") == "BUG-7 Title Field Test", (
            f"BUG-7 REGRESSION: title not reflected in response: {body.get('title')!r}"
        )

    def test_frontend_upload_page_appends_title(self):
        """Upload page source must have form.append('title', ...) before fetch."""
        upload_page = Path(
            "/home/sawan/arukai-capital-call/frontend/src/app/documents/upload/page.tsx"
        )
        if not upload_page.exists():
            pytest.skip("Upload page not found")
        src = upload_page.read_text()
        assert 'form.append("title"' in src or "form.append('title'" in src, (
            'BUG-7 REGRESSION: upload/page.tsx does not call form.append("title", ...). '
            "The title field will be missing from the upload request."
        )


# ---------------------------------------------------------------------------
# BUG-8: Haiku model ID is correct
# ---------------------------------------------------------------------------

class TestBug8HaikuModelId:
    """
    BUG-8: The wrong model ID was passed to Anthropic API calls, causing
    model-not-found errors that silently fell back and produced wrong results.
    Correct ID: claude-haiku-4-5-20251001
    """

    EXPECTED_MODEL_ID = "claude-haiku-4-5-20251001"
    CLASSIFY_MODULE = Path("/home/sawan/arukai-capital-call/backend/app/classify.py")

    def test_classify_module_uses_correct_model_id(self):
        """classify.py must define HAIKU_MODEL = 'claude-haiku-4-5-20251001'."""
        assert self.CLASSIFY_MODULE.exists(), f"classify.py not found at {self.CLASSIFY_MODULE}"
        src = self.CLASSIFY_MODULE.read_text()
        assert f'"{self.EXPECTED_MODEL_ID}"' in src or f"'{self.EXPECTED_MODEL_ID}'" in src, (
            f"BUG-8 REGRESSION: Model ID '{self.EXPECTED_MODEL_ID}' not found in classify.py. "
            "Check HAIKU_MODEL constant."
        )

    def test_haiku_model_constant_imported_correctly(self):
        """Import classify module and verify HAIKU_MODEL value matches spec."""
        import importlib.util
        spec_path = self.CLASSIFY_MODULE
        spec = importlib.util.spec_from_file_location("classify_check", spec_path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        # Don't execute (would try to init anthropic client) — just grep the source
        src = spec_path.read_text()
        # Extract HAIKU_MODEL = "..." assignment
        match = re.search(r'HAIKU_MODEL\s*=\s*["\']([^"\']+)["\']', src)
        assert match, "BUG-8 REGRESSION: Could not find HAIKU_MODEL assignment in classify.py"
        actual = match.group(1)
        assert actual == self.EXPECTED_MODEL_ID, (
            f"BUG-8 REGRESSION: HAIKU_MODEL is '{actual}', expected '{self.EXPECTED_MODEL_ID}'."
        )

    def test_no_old_model_id_in_classify(self):
        """No deprecated model IDs (claude-haiku-20240307 etc.) in classify.py."""
        src = self.CLASSIFY_MODULE.read_text()
        banned_ids = [
            "claude-haiku-20240307",
            "claude-3-haiku",
            "claude-3-haiku-20240307",
            "claude-instant",
        ]
        for banned in banned_ids:
            assert banned not in src, (
                f"BUG-8 REGRESSION: Deprecated model ID '{banned}' found in classify.py. "
                "Update to claude-haiku-4-5-20251001."
            )

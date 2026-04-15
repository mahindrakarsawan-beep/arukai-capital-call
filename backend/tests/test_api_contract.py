"""
Contract test — Rule 15.

For every URL path that the frontend (api.ts) calls, assert that the
corresponding route exists in the backend with the matching HTTP method.

Paths containing template literals like `${id}` are converted to a regex
pattern and matched against backend routes rather than exact-string compared.
"""
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FRONTEND_API_TS = Path("/home/sawan/arukai-capital-call/frontend/src/lib/api.ts")

# Regex to find  fetch(`${API_BASE}/some/path`, ...)
#   or            fetch(`${API_BASE}/some/${id}/path`, ...)
# and also the string variant  `${API_BASE}/documents/${id}/pdf`
# returned from plain functions (not fetch calls directly).
_FETCH_PATTERN = re.compile(
    r"""`\$\{API_BASE\}(/[^`"'\s)]+)`""",
)

# Template-literal variable segments like ${id}, ${someVar}
_TEMPLATE_VAR = re.compile(r"\$\{[^}]+\}")

# HTTP method from the fetch options object  method: "POST"
# We want to pair URLs with their methods.
_METHOD_PATTERN = re.compile(r'method:\s*"([A-Z]+)"')


def _extract_frontend_calls(src: str) -> list[tuple[str, str]]:
    """
    Return a list of (method, path_template) tuples from api.ts.

    We scan each fetch/return-url occurrence and look backwards for a
    method: "..." in the same call block (within 5 lines).  If no method is
    found, it defaults to GET.
    """
    calls: list[tuple[str, str]] = []
    lines = src.splitlines()

    for line_no, line in enumerate(lines):
        m = _FETCH_PATTERN.search(line)
        if not m:
            continue

        raw_path = m.group(1)

        # Determine the HTTP method by scanning the surrounding context
        # (up to 6 lines forward and the same line).
        context = "\n".join(lines[line_no : line_no + 7])
        method_match = _METHOD_PATTERN.search(context)
        method = method_match.group(1) if method_match else "GET"

        calls.append((method, raw_path))

    return calls


def _path_to_pattern(path_template: str) -> re.Pattern:
    """
    Convert a frontend path template like  /documents/${id}/pdf
    into a regex that matches the corresponding backend route path
    like  /documents/{pkg_id}/pdf.
    """
    # Escape everything, then replace the escaped variable placeholder
    escaped = re.escape(path_template)
    # re.escape turns ${id} into \$\{id\}  — replace that with [^/]+
    escaped = re.sub(r"\\\$\\\{[^}]+\\}", r"[^/]+", escaped)
    return re.compile(r"^" + escaped + r"$")


def _collect_backend_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Return list of (method, path) for every APIRoute in the app."""
    result = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or []:
                result.append((method.upper(), route.path))
    return result


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_frontend_backend_contract():
    """Every path+method used in frontend/src/lib/api.ts must exist in the backend."""
    # Import app after env vars set by conftest
    from app.main import app  # noqa: E402

    assert FRONTEND_API_TS.exists(), f"api.ts not found at {FRONTEND_API_TS}"

    src = FRONTEND_API_TS.read_text()
    frontend_calls = _extract_frontend_calls(src)
    assert frontend_calls, "No fetch URLs extracted from api.ts — check the regex"

    backend_routes = _collect_backend_routes(app)
    backend_route_set = {(m, p) for m, p in backend_routes}

    failures = []
    for method, path_template in frontend_calls:
        has_template_var = bool(_TEMPLATE_VAR.search(path_template))

        if has_template_var:
            # Pattern match against backend routes
            pattern = _path_to_pattern(path_template)
            matched = any(
                bm == method and pattern.match(bp)
                for bm, bp in backend_routes
            )
            if not matched:
                failures.append(
                    f"  {method} {path_template!r}  "
                    f"(no backend route matches pattern {pattern.pattern!r})"
                )
        else:
            # Exact match
            if (method, path_template) not in backend_route_set:
                failures.append(f"  {method} {path_template!r}  (not found in backend)")

    if failures:
        route_list = "\n".join(f"  {m} {p}" for m, p in sorted(backend_route_set))
        pytest.fail(
            "Frontend–backend contract violations:\n"
            + "\n".join(failures)
            + f"\n\nAvailable backend routes:\n{route_list}"
        )

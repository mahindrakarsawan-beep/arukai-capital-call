#!/usr/bin/env python3
"""
Rule 15 — Frontend ↔ Backend API contract check.

For every URL path the frontend (`frontend/src/lib/api.ts`) calls, assert that
the corresponding route exists in the backend with the matching HTTP method.

Runs standalone (no pytest). Emits the governance-required `RULE 15 — API
CONTRACT CHECK` section so Miller can paste the output directly into the
H9 Production Smoke Report §4 evidence block.

Exit codes:
  0  contract holds
  1  one or more frontend calls lack a matching backend route
  2  setup error (cannot locate app.main or api.ts)

Invocation:
  cd backend && python ../scripts/contract_check.py
  # or from repo root:
  PYTHONPATH=backend python scripts/contract_check.py

Reference:
  - `.squad/decisions/inbox/holden-copilot-kpi-and-rules-v2.md` (Rule 15 origin)
  - `.squad/ARU-16-incident-report.md` (the defect class this gate prevents)
  - `backend/tests/test_api_contract.py` (pytest equivalent)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Env + path bootstrap — must run before importing app.main
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_API_TS = REPO_ROOT / "frontend" / "src" / "lib" / "api.ts"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "contract-check-transient-secret")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_FETCH_PATTERN = re.compile(r"""`\$\{API_BASE\}(/[^`"'\s)]+)`""")
_DYNAMIC_SUFFIX_PATTERN = re.compile(r"""`\$\{API_BASE\}(/[A-Za-z0-9_/.-]+)\$\{""")
_TEMPLATE_VAR = re.compile(r"\$\{[^}]+\}")
_METHOD_PATTERN = re.compile(r'method:\s*"([A-Z]+)"')


def extract_frontend_calls(src: str) -> list[tuple[str, str]]:
    """Return a list of (method, path_template) tuples from api.ts."""
    calls: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    lines = src.splitlines()

    for line_no, line in enumerate(lines):
        m = _FETCH_PATTERN.search(line)
        if m:
            raw_path = m.group(1)
            context = "\n".join(lines[line_no : line_no + 7])
            method_match = _METHOD_PATTERN.search(context)
            method = method_match.group(1) if method_match else "GET"
            key = (method, raw_path)
            if key not in seen:
                seen.add(key)
                calls.append(key)
            continue

        m2 = _DYNAMIC_SUFFIX_PATTERN.search(line)
        if m2:
            raw_path = m2.group(1)
            context = "\n".join(lines[line_no : line_no + 7])
            method_match = _METHOD_PATTERN.search(context)
            method = method_match.group(1) if method_match else "GET"
            key = (method, raw_path)
            if key not in seen:
                seen.add(key)
                calls.append(key)

    return calls


def path_to_pattern(path_template: str) -> re.Pattern:
    """Convert `/documents/${id}/pdf` into a regex matching `/documents/{x}/pdf`."""
    escaped = re.escape(path_template)
    escaped = re.sub(r"\\\$\\\{[^}]+\\}", r"[^/]+", escaped)
    return re.compile(r"^" + escaped + r"$")


def collect_backend_routes(app) -> list[tuple[str, str]]:
    """Return (method, path) for every APIRoute in the FastAPI app."""
    from fastapi.routing import APIRoute

    result: list[tuple[str, str]] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or []:
                result.append((method.upper(), route.path))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 72)
    print("RULE 15 — API CONTRACT CHECK")
    print("=" * 72)

    if not FRONTEND_API_TS.exists():
        print(f"ERROR: api.ts not found at {FRONTEND_API_TS}", file=sys.stderr)
        return 2

    try:
        from app.main import app
    except Exception as exc:
        print(f"ERROR: could not import app.main ({exc})", file=sys.stderr)
        print(
            "HINT: run from the backend/ directory, or set PYTHONPATH=backend.",
            file=sys.stderr,
        )
        return 2

    src = FRONTEND_API_TS.read_text(encoding="utf-8")
    frontend_calls = extract_frontend_calls(src)
    if not frontend_calls:
        print("ERROR: no fetch URLs extracted from api.ts — check the regex",
              file=sys.stderr)
        return 2

    backend_routes = collect_backend_routes(app)
    backend_route_set = {(m, p) for m, p in backend_routes}

    failures: list[str] = []
    for method, path_template in frontend_calls:
        has_template_var = bool(_TEMPLATE_VAR.search(path_template))

        if has_template_var:
            pattern = path_to_pattern(path_template)
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
            if (method, path_template) not in backend_route_set:
                failures.append(f"  {method} {path_template!r}  (not found in backend)")

    print(
        f"Checked {len(frontend_calls)} frontend calls against "
        f"{len(backend_routes)} backend routes."
    )

    if failures:
        print()
        print(f"FAIL — {len(failures)} contract violation(s):")
        for f in failures:
            print(f)
        print()
        print("Available backend routes:")
        for m, p in sorted(backend_route_set):
            print(f"  {m} {p}")
        print()
        print("RESULT: FAIL")
        return 1

    print("RESULT: PASS — every frontend call maps to a backend route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Arukai Independent QA Verifier

An adversarial verification agent that runs OUTSIDE the squad's testing bubble.
Uses the Mistral API for independent code review and live deployment verification.

Purpose: Catch the class of bugs the squad keeps missing — where mocked tests
pass but real integration fails (POR-146, display bugs, v0.1→v0.2 state drift).

Usage:
    # Live deployment smoke (no Mistral needed)
    python3 scripts/qa_verifier.py --smoke --backend-url https://...backend... --frontend-url https://...frontend...

    # Full verification with Mistral code review
    python3 scripts/qa_verifier.py --full --backend-url https://... --frontend-url https://... --mistral-key $MISTRAL_API_KEY

    # Contract drift check only (no live deployment needed)
    python3 scripts/qa_verifier.py --contract
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    severity: str = "medium"  # low, medium, high, critical


@dataclass
class VerificationReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult):
        self.checks.append(result)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity in ("high", "critical"))

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def print_report(self):
        print("\n" + "=" * 70)
        print("ARUKAI INDEPENDENT QA VERIFICATION REPORT")
        print("=" * 70)

        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            icon = "✓" if c.passed else "✗"
            print(f"\n  [{status}] {icon} {c.name} ({c.severity})")
            if not c.passed or c.severity == "critical":
                for line in c.details.split("\n"):
                    print(f"         {line}")

        print(f"\n{'=' * 70}")
        total_pass = sum(1 for c in self.checks if c.passed)
        verdict = "PASS" if self.passed else "FAIL"
        print(f"  {total_pass}/{self.total} checks passed — VERDICT: {verdict}")
        if self.failures:
            print(f"  {len(self.failures)} failures:")
            for f in self.failures:
                print(f"    - [{f.severity}] {f.name}")
        print("=" * 70 + "\n")
        return self.passed


# ---------------------------------------------------------------------------
# 1. LIVE DEPLOYMENT SMOKE
# ---------------------------------------------------------------------------

def _fetch(url: str, method: str = "GET", headers: dict = None, body: bytes = None, timeout: int = 10):
    """Simple HTTP fetch without requests library."""
    req = Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.status, resp.read().decode("utf-8")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except URLError as e:
        return 0, str(e)


def _fetch_json(url: str, method: str = "GET", headers: dict = None, body: dict = None, timeout: int = 10):
    """Fetch and parse JSON response."""
    body_bytes = json.dumps(body).encode() if body else None
    hdrs = headers or {}
    if body:
        hdrs["Content-Type"] = "application/json"
    status, text = _fetch(url, method, hdrs, body_bytes, timeout)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = None
    return status, data, text


def smoke_backend(backend_url: str, report: VerificationReport):
    """Hit every backend endpoint and verify responses make sense."""

    # 1. Health
    status, data, _ = _fetch_json(f"{backend_url}/health")
    report.add(CheckResult(
        "Backend health",
        status == 200 and data and data.get("status") == "ok",
        f"HTTP {status}, response: {data}",
        "critical"
    ))

    # 2. Login all 3 roles
    tokens = {}
    for role, email, password in [
        ("admin", "admin@arukai.example", "admin123"),
        ("reviewer", "reviewer@arukai.example", "reviewer123"),
        ("approver", "approver@arukai.example", "approver123"),
    ]:
        status, data, _ = _fetch_json(
            f"{backend_url}/auth/login",
            method="POST",
            body={"email": email, "password": password}
        )
        got_role = data.get("role") if data else None
        report.add(CheckResult(
            f"Login as {role}",
            status == 200 and got_role == role,
            f"HTTP {status}, role={got_role}",
            "critical"
        ))
        if status == 200 and data:
            tokens[role] = data.get("access_token")

    if not tokens.get("admin"):
        report.add(CheckResult("Skipping auth'd checks", False, "No admin token", "critical"))
        return

    auth = {"Authorization": f"Bearer {tokens['admin']}"}

    # 3. List packages — verify response shape includes classification data
    status, data, raw = _fetch_json(f"{backend_url}/packages", headers=auth)
    has_classification_fields = False
    if status == 200 and isinstance(data, list):
        if len(data) > 0:
            first = data[0]
            has_classification_fields = "doc_type" in first and "confidence" in first and "filename" in first
        else:
            has_classification_fields = True  # empty list is ok

    report.add(CheckResult(
        "GET /packages includes classification summary",
        status == 200 and has_classification_fields,
        f"HTTP {status}, {len(data) if isinstance(data, list) else 0} packages, has doc_type/confidence/filename: {has_classification_fields}",
        "critical"
    ))

    # 4. Verify v0.2 states (not v0.1)
    v01_states = {"pending_review", "pending_classification"}
    has_v01_states = False
    v02_states_found = set()
    if isinstance(data, list):
        for pkg in data:
            state = pkg.get("state", "")
            if state in v01_states:
                has_v01_states = True
            v02_states_found.add(state)

    report.add(CheckResult(
        "Packages use v0.2 states (not v0.1)",
        not has_v01_states and len(v02_states_found) > 0,
        f"States found: {v02_states_found}, v0.1 states present: {has_v01_states}",
        "critical"
    ))

    # 5. Admin sees all packages (not filtered to own)
    # Login as reviewer, upload something, then check admin can see it
    reviewer_auth = {"Authorization": f"Bearer {tokens.get('reviewer', '')}"}
    status_r, data_r, _ = _fetch_json(f"{backend_url}/packages", headers=reviewer_auth)
    status_a, data_a, _ = _fetch_json(f"{backend_url}/packages", headers=auth)
    admin_sees_all = True
    if isinstance(data_r, list) and isinstance(data_a, list):
        reviewer_ids = {p["id"] for p in data_r}
        admin_ids = {p["id"] for p in data_a}
        admin_sees_all = reviewer_ids.issubset(admin_ids)

    report.add(CheckResult(
        "Admin sees all packages (not filtered)",
        admin_sees_all,
        f"Reviewer sees {len(data_r) if isinstance(data_r, list) else '?'}, Admin sees {len(data_a) if isinstance(data_a, list) else '?'}",
        "high"
    ))

    # 6. Audit endpoint — admin can access
    status, _, _ = _fetch_json(f"{backend_url}/audit", headers=auth)
    report.add(CheckResult(
        "GET /audit accessible to admin",
        status == 200,
        f"HTTP {status}",
        "high"
    ))

    # 7. Audit endpoint — reviewer CANNOT access (S5)
    status, _, _ = _fetch_json(f"{backend_url}/audit", headers=reviewer_auth)
    report.add(CheckResult(
        "GET /audit blocked for reviewer (S5)",
        status in (403, 401),
        f"HTTP {status} (expected 403)",
        "high"
    ))

    # 8. Deprecated approvals endpoint returns 410
    status, _, _ = _fetch_json(
        f"{backend_url}/approvals/00000000-0000-0000-0000-000000000000",
        method="POST",
        headers={**auth, "Content-Type": "application/json"},
        body={"action": "approve"}
    )
    report.add(CheckResult(
        "Deprecated /approvals returns 410 Gone",
        status == 410,
        f"HTTP {status}",
        "medium"
    ))


def smoke_frontend(frontend_url: str, report: VerificationReport):
    """Basic frontend accessibility checks."""

    # 1. Frontend loads
    status, body = _fetch(frontend_url)
    report.add(CheckResult(
        "Frontend loads (HTTP 200)",
        status == 200,
        f"HTTP {status}",
        "critical"
    ))

    # 2. No "localhost" baked into the frontend bundle
    has_localhost = "localhost:8000" in body if body else True
    report.add(CheckResult(
        "No localhost:8000 in frontend HTML",
        not has_localhost,
        "Found localhost:8000 in response" if has_localhost else "Clean",
        "critical"
    ))

    # 3. Arukai language present (not generic SaaS)
    has_arukai = "Arukai" in body if body else False
    report.add(CheckResult(
        "Arukai branding present",
        has_arukai,
        "Found 'Arukai' in HTML" if has_arukai else "Missing Arukai branding",
        "high"
    ))


# ---------------------------------------------------------------------------
# 2. CONTRACT DRIFT DETECTION
# ---------------------------------------------------------------------------

def check_contract(report: VerificationReport, repo_root: str = "."):
    """Parse frontend api.ts fetch calls and verify backend has matching routes."""

    api_ts = Path(repo_root) / "frontend" / "src" / "lib" / "api.ts"
    if not api_ts.exists():
        report.add(CheckResult("Contract: api.ts exists", False, f"Not found: {api_ts}", "critical"))
        return

    content = api_ts.read_text()

    # Extract fetch calls: fetch(`${API_BASE}/path`, { method: "POST" })
    # Also: apiGet, apiPost patterns
    fetch_pattern = re.compile(
        r'fetch\(\s*`\$\{API_BASE\}(/[^`]+)`.*?method:\s*["\'](\w+)["\']',
        re.DOTALL
    )
    simple_fetch = re.compile(
        r'fetch\(\s*`\$\{API_BASE\}(/[^`]+)`'
    )

    calls = []
    for m in fetch_pattern.finditer(content):
        path = m.group(1).replace("${id}", "{id}").replace("${pkg_id}", "{pkg_id}")
        method = m.group(2).upper()
        calls.append((method, path))

    # GET calls (no method specified = GET)
    for m in simple_fetch.finditer(content):
        path = m.group(1).replace("${id}", "{id}").replace("${pkg_id}", "{pkg_id}")
        if not any(c[1] == path for c in calls):
            calls.append(("GET", path))

    if not calls:
        report.add(CheckResult("Contract: found API calls", False, "No fetch calls found in api.ts", "critical"))
        return

    report.add(CheckResult(
        f"Contract: found {len(calls)} API calls in api.ts",
        True,
        ", ".join(f"{m} {p}" for m, p in calls),
        "medium"
    ))

    # Now check backend routes
    try:
        sys.path.insert(0, str(Path(repo_root) / "backend"))
        from app.main import create_app
        app = create_app()

        backend_routes = set()
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    backend_routes.add((method, route.path))

        for method, path in calls:
            # Normalize path params
            normalized = re.sub(r'\{[^}]+\}', '{id}', path)
            found = False
            for bm, bp in backend_routes:
                bn = re.sub(r'\{[^}]+\}', '{id}', bp)
                if bm == method and bn == normalized:
                    found = True
                    break

            report.add(CheckResult(
                f"Contract: {method} {path}",
                found,
                "Route exists in backend" if found else f"NO MATCHING BACKEND ROUTE for {method} {path}",
                "critical" if not found else "low"
            ))
    except Exception as e:
        report.add(CheckResult("Contract: backend import", False, str(e), "high"))


# ---------------------------------------------------------------------------
# 3. MISTRAL CODE REVIEW (optional)
# ---------------------------------------------------------------------------

def _build_review_prompt(files_to_review: dict) -> str:
    """Build the shared review prompt for both Mistral and OpenAI."""
    return f"""You are an independent QA reviewer for a web application. The development team keeps shipping integration bugs:
1. Frontend expects one API response shape but backend returns another
2. Frontend handles old state values but backend sends new ones
3. Mocked tests pass but real API calls fail

Review these frontend integration files and flag SPECIFIC risks:

--- api.ts (the API client — every fetch call the frontend makes) ---
{files_to_review.get('api.ts', 'NOT FOUND')}

--- state.ts (maps backend states to UI display) ---
{files_to_review.get('state.ts', 'NOT FOUND')}

For each risk found, output: RISK: [specific description with line reference if possible]
If the code looks correct, output: CLEAN"""


def _call_llm(url: str, api_key: str, model: str, prompt: str, provider: str) -> str:
    """Generic LLM API call for OpenAI-compatible endpoints."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.1
    }).encode()

    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if provider == "mistral":
        req.add_header("Authorization", f"Bearer {api_key}")
    else:
        req.add_header("Authorization", f"Bearer {api_key}")

    resp = urlopen(req, timeout=60)
    result = json.loads(resp.read().decode())
    return result["choices"][0]["message"]["content"]


def _run_llm_review(provider: str, model: str, url: str, api_key: str,
                     files_to_review: dict, report: VerificationReport):
    """Run an independent code review via a specific LLM provider."""
    prompt = _build_review_prompt(files_to_review)

    try:
        review_text = _call_llm(url, api_key, model, prompt, provider)
        risks = [line.strip() for line in review_text.split("\n") if line.strip().startswith("RISK:")]

        report.add(CheckResult(
            f"{provider.capitalize()} independent review ({model})",
            len(risks) == 0,
            review_text[:500],
            "high" if risks else "low"
        ))

        for risk in risks:
            report.add(CheckResult(
                f"{provider.capitalize()} risk: {risk[5:80]}...",
                False,
                risk,
                "high"
            ))
    except Exception as e:
        report.add(CheckResult(f"{provider.capitalize()} review: API call", False, str(e), "medium"))


def independent_reviews(repo_root: str, mistral_key: str, openai_key: str, report: VerificationReport):
    """Run independent code reviews via Mistral AND OpenAI (not Anthropic — that powers the squad)."""

    api_ts = Path(repo_root) / "frontend" / "src" / "lib" / "api.ts"
    state_ts = Path(repo_root) / "frontend" / "src" / "lib" / "state.ts"

    files_to_review = {}
    for f in [api_ts, state_ts]:
        if f.exists():
            files_to_review[f.name] = f.read_text()[:4000]

    if not files_to_review:
        report.add(CheckResult("Independent review: files found", False, "No files to review", "medium"))
        return

    if mistral_key:
        print("  Running Mistral review...")
        _run_llm_review(
            "mistral", "mistral-small-latest",
            "https://api.mistral.ai/v1/chat/completions",
            mistral_key, files_to_review, report
        )
    else:
        print("  Skipping Mistral (no key)")

    if openai_key:
        print("  Running OpenAI review...")
        _run_llm_review(
            "openai", "gpt-4o-mini",
            "https://api.openai.com/v1/chat/completions",
            openai_key, files_to_review, report
        )
    else:
        print("  Skipping OpenAI (no key)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Arukai Independent QA Verifier")
    parser.add_argument("--smoke", action="store_true", help="Run live deployment smoke tests")
    parser.add_argument("--contract", action="store_true", help="Run contract drift detection")
    parser.add_argument("--full", action="store_true", help="Run all checks including Mistral review")
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_URL", ""))
    parser.add_argument("--frontend-url", default=os.environ.get("FRONTEND_URL", ""))
    parser.add_argument("--mistral-key", default=os.environ.get("MISTRAL_API_KEY", ""))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    report = VerificationReport()

    if args.smoke or args.full:
        if not args.backend_url:
            print("ERROR: --backend-url required for smoke tests")
            sys.exit(1)
        print(f"\n--- Smoke testing backend: {args.backend_url}")
        smoke_backend(args.backend_url, report)

        if args.frontend_url:
            print(f"--- Smoke testing frontend: {args.frontend_url}")
            smoke_frontend(args.frontend_url, report)

    if args.contract or args.full:
        print(f"--- Contract drift check: {args.repo_root}")
        check_contract(report, args.repo_root)

    if args.full and (args.mistral_key or args.openai_key):
        print("--- Independent code reviews (Mistral + OpenAI, NOT Anthropic)")
        independent_reviews(args.repo_root, args.mistral_key, args.openai_key, report)
    elif args.full:
        print("--- Skipping independent reviews (no --mistral-key or --openai-key)")

    passed = report.print_report()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

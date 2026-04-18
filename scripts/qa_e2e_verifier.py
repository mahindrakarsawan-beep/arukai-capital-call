#!/usr/bin/env python3
"""
Arukai Independent E2E Verifier

Uses Playwright to walk every user journey in a REAL BROWSER against the live deployment,
captures screenshots at each step, then sends screenshots + DOM snapshots to Mistral AND
OpenAI for independent UX validation.

This is NOT unit testing. This is: "open the app as a real user, try every flow,
screenshot what you see, and ask two independent AIs if it looks broken."

Usage:
    python3 scripts/qa_e2e_verifier.py \
        --frontend-url https://...frontend... \
        --backend-url https://...backend... \
        --mistral-key $MISTRAL_API_KEY \
        --openai-key $OPENAI_API_KEY \
        --output-dir ./qa_screenshots
"""

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


@dataclass
class StepResult:
    step: str
    role: str
    screenshot_path: str
    dom_summary: str
    passed: bool
    details: str
    ai_verdicts: dict = field(default_factory=dict)  # {provider: verdict}


@dataclass
class E2EReport:
    steps: list[StepResult] = field(default_factory=list)

    def add(self, step: StepResult):
        self.steps.append(step)

    def print_report(self):
        print("\n" + "=" * 70)
        print("ARUKAI E2E EXPERIENCE VERIFICATION")
        print("=" * 70)
        for s in self.steps:
            icon = "✓" if s.passed else "✗"
            print(f"\n  [{s.role}] {icon} {s.step}")
            print(f"         Screenshot: {s.screenshot_path}")
            if not s.passed:
                print(f"         ISSUE: {s.details}")
            for provider, verdict in s.ai_verdicts.items():
                status = "OK" if "PASS" in verdict[:20].upper() else "ISSUE"
                print(f"         {provider}: {verdict[:200]}")

        failures = [s for s in self.steps if not s.passed]
        ai_flags = [s for s in self.steps
                    if any("FAIL" in v.upper() or "RISK" in v.upper() or "ISSUE" in v.upper()
                           for v in s.ai_verdicts.values())]

        print(f"\n{'=' * 70}")
        print(f"  Steps: {len(self.steps)} | Failures: {len(failures)} | AI flags: {len(ai_flags)}")
        verdict = "PASS" if not failures and not ai_flags else "FAIL"
        print(f"  VERDICT: {verdict}")
        print("=" * 70 + "\n")
        return verdict == "PASS"


def _call_llm_with_image(provider: str, api_key: str, model: str,
                          prompt: str, image_b64: str) -> str:
    """Send screenshot + prompt to Mistral or OpenAI for UX evaluation."""

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{image_b64}"
            }}
        ]
    }]

    if provider == "mistral":
        url = "https://api.mistral.ai/v1/chat/completions"
        model = "pixtral-12b-2409"  # Mistral's vision model
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"

    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.1
    }).encode()

    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        resp = urlopen(req, timeout=60)
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def run_e2e(frontend_url: str, backend_url: str, output_dir: str,
            mistral_key: str, openai_key: str) -> E2EReport:
    """Run full E2E walkthrough via Playwright, screenshot each step, send to AI reviewers."""

    report = E2EReport()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    ux_prompt = """You are an independent UX quality reviewer for a private financial workflow application called "Arukai Capital Call."

This is NOT a generic SaaS app. It should feel like:
- Boutique private banking / family office software
- Restrained, premium, editorial
- Every status implies a next owner
- Every AI output shows confidence
- No bright SaaS gradients or generic "upload" language

Look at this screenshot and evaluate:
1. Does it feel like a private workflow atelier or a generic admin dashboard?
2. Are there any broken UI elements, missing data, or error states visible?
3. Is the information hierarchy clear? Can the user immediately see what needs attention?
4. Any generic SaaS language? (upload, submit, success, processing, click)
5. Is the visual quality premium or utilitarian?

Reply with:
PASS: [one sentence why it's acceptable]
or
FAIL: [specific issues found]"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        roles = [
            ("admin", "admin@arukai.example", "admin123"),
            ("reviewer", "reviewer@arukai.example", "reviewer123"),
            ("approver", "approver@arukai.example", "approver123"),
        ]

        for role, email, password in roles:
            print(f"\n--- Walking as {role} ---")

            # Step 1: Login page
            page.goto(frontend_url)
            page.wait_for_load_state("networkidle")
            ss_path = str(out / f"{role}-01-login.png")
            page.screenshot(path=ss_path, full_page=True)

            step = StepResult(
                step="Login page",
                role=role,
                screenshot_path=ss_path,
                dom_summary=page.title(),
                passed=True,
                details=""
            )

            # Check for Arukai language
            body_text = page.inner_text("body")
            if "Sign in" in body_text:
                step.passed = False
                step.details = "Found 'Sign in' — should be 'Enter workflow'"
            if "Arukai" not in body_text:
                step.passed = False
                step.details += " | Missing 'Arukai' branding"

            report.add(step)

            # Step 2: Log in
            try:
                page.fill('[placeholder*="name@"]', email)
                page.fill('[placeholder*="••"]', password)
                page.click('button:has-text("Enter workflow")')
                page.wait_for_url("**/documents**", timeout=10000)
            except Exception as e:
                try:
                    page.fill('input[type="email"], input[name="email"], [placeholder*="email"]', email)
                    page.fill('input[type="password"], [placeholder*="password"]', password)
                    page.click('button[type="submit"], button:has-text("Sign"), button:has-text("Enter")')
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                except Exception as e2:
                    report.add(StepResult(
                        step="Login submit",
                        role=role,
                        screenshot_path="",
                        dom_summary="",
                        passed=False,
                        details=f"Login failed: {e2}"
                    ))
                    continue

            # Step 3: Console / Dashboard
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            ss_path = str(out / f"{role}-02-console.png")
            page.screenshot(path=ss_path, full_page=True)

            body_text = page.inner_text("body")
            step = StepResult(
                step="Operations console",
                role=role,
                screenshot_path=ss_path,
                dom_summary=body_text[:500],
                passed=True,
                details=""
            )

            # Check console quality
            issues = []
            if "Unclassified" in body_text and body_text.count("Unclassified") > 2:
                issues.append(f"'{body_text.count('Unclassified')}x Unclassified' badges — classification data not rendering")
            if body_text.count("—") > 5:
                issues.append("Multiple em-dashes where data should be — fields not populated")
            if "Upload" in body_text:
                issues.append("Found 'Upload' — banned SaaS language")
            if "Operations console" not in body_text and "Console" not in body_text:
                issues.append("Missing 'Operations console' heading")

            # Role-specific checks
            if role == "reviewer" and "Claim" not in body_text and "claim" not in body_text:
                issues.append("Reviewer view missing 'Claim to review' CTA")
            if role == "approver" and "attestation" not in body_text.lower() and "approval" not in body_text.lower():
                issues.append("Approver view not emphasizing pending attestations")
            if role == "admin" and "Audit" not in body_text:
                issues.append("Admin view missing audit ledger link")

            if issues:
                step.passed = False
                step.details = " | ".join(issues)

            report.add(step)

            # Step 4: Click into a package (if any exist)
            try:
                links = page.query_selector_all('a[href*="/documents/"]')
                if links:
                    links[0].click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    ss_path = str(out / f"{role}-03-detail.png")
                    page.screenshot(path=ss_path, full_page=True)

                    body_text = page.inner_text("body")
                    step = StepResult(
                        step="Package detail",
                        role=role,
                        screenshot_path=ss_path,
                        dom_summary=body_text[:500],
                        passed=True,
                        details=""
                    )

                    detail_issues = []
                    if "No classification data" in body_text:
                        detail_issues.append("Shows 'No classification data' — extraction not rendering")
                    if "Source document" not in body_text and "Source" not in body_text:
                        detail_issues.append("Missing source document block")
                    if "Extracted facts" not in body_text and "extracted" not in body_text.lower():
                        detail_issues.append("Missing extracted facts block")
                    if "Audit" not in body_text and "audit" not in body_text.lower():
                        detail_issues.append("Missing audit trail block")

                    if detail_issues:
                        step.passed = False
                        step.details = " | ".join(detail_issues)

                    report.add(step)

                    # Go back to console
                    page.go_back()
                    page.wait_for_load_state("networkidle")
            except Exception as e:
                report.add(StepResult(
                    step="Package detail navigation",
                    role=role,
                    screenshot_path="",
                    dom_summary="",
                    passed=False,
                    details=str(e)
                ))

            # Step 5: Audit ledger (admin/approver only)
            if role in ("admin", "approver"):
                try:
                    audit_link = page.query_selector('a[href*="/audit"]')
                    if audit_link:
                        audit_link.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(1)
                        ss_path = str(out / f"{role}-04-audit.png")
                        page.screenshot(path=ss_path, full_page=True)

                        body_text = page.inner_text("body")
                        step = StepResult(
                            step="Audit ledger",
                            role=role,
                            screenshot_path=ss_path,
                            dom_summary=body_text[:300],
                            passed="Audit" in body_text or "audit" in body_text,
                            details="" if "Audit" in body_text else "Audit ledger not loading"
                        )
                        report.add(step)
                    else:
                        report.add(StepResult(
                            step="Audit ledger link",
                            role=role,
                            screenshot_path="",
                            dom_summary="",
                            passed=False,
                            details="No audit ledger link found in nav"
                        ))
                except Exception as e:
                    report.add(StepResult(
                        step="Audit ledger",
                        role=role,
                        screenshot_path="",
                        dom_summary="",
                        passed=False,
                        details=str(e)
                    ))

            # Log out
            try:
                logout_btn = page.query_selector('button:has-text("Leave workflow"), button:has-text("Sign out"), button:has-text("Logout")')
                if logout_btn:
                    logout_btn.click()
                    page.wait_for_load_state("networkidle")
                else:
                    page.goto(frontend_url)
            except:
                page.goto(frontend_url)

        # Now send screenshots to AI reviewers
        print("\n--- Sending screenshots to AI reviewers ---")
        for step in report.steps:
            if step.screenshot_path and Path(step.screenshot_path).exists():
                img_b64 = base64.b64encode(Path(step.screenshot_path).read_bytes()).decode()

                for provider, key, label in [
                    ("mistral", mistral_key, "Mistral"),
                    ("openai", openai_key, "OpenAI"),
                ]:
                    if key:
                        try:
                            verdict = _call_llm_with_image(provider, key, "", ux_prompt, img_b64)
                            step.ai_verdicts[label] = verdict
                        except Exception as e:
                            step.ai_verdicts[label] = f"ERROR: {e}"

        browser.close()

    return report


def main():
    parser = argparse.ArgumentParser(description="Arukai E2E Experience Verifier")
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--backend-url", default="")
    parser.add_argument("--mistral-key", default=os.environ.get("MISTRAL_API_KEY", ""))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--output-dir", default="./qa_screenshots")
    args = parser.parse_args()

    report = run_e2e(
        args.frontend_url,
        args.backend_url,
        args.output_dir,
        args.mistral_key,
        args.openai_key
    )

    passed = report.print_report()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

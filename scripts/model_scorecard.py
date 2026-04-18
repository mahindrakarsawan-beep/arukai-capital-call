#!/usr/bin/env python3
"""
Arukai Model Scorecard — Exhaustive multi-category benchmark

Tests every model across 7 categories with real tasks, not synthetic benchmarks.
Each category uses a task the squad actually performs.

Categories:
1. Document extraction (classify + extract fields from a capital call PDF)
2. Code generation (write a FastAPI endpoint from a spec)
3. Code validation (find bugs in a code snippet)
4. Testing (write pytest tests from function signature)
5. Logic/reasoning (evaluate a state machine transition)
6. Product management (write acceptance criteria from a user story)
7. UX design (critique a UI screenshot and suggest improvements)

Usage:
    python3 scripts/model_scorecard.py \
        --anthropic-key $ANTHROPIC_API_KEY \
        --openai-key $OPENAI_API_KEY \
        --mistral-key $MISTRAL_API_KEY
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# Pricing (per 1M tokens, as of 2026-04)
# ---------------------------------------------------------------------------
MODELS = {
    # Anthropic
    "claude-opus-4-6": {"provider": "anthropic", "input": 15.00, "output": 75.00, "tier": "premium"},
    "claude-sonnet-4-6": {"provider": "anthropic", "input": 3.00, "output": 15.00, "tier": "standard"},
    "claude-haiku-4-5-20251001": {"provider": "anthropic", "input": 0.80, "output": 4.00, "tier": "fast"},
    # OpenAI
    "gpt-4o": {"provider": "openai", "input": 2.50, "output": 10.00, "tier": "premium"},
    "gpt-4o-mini": {"provider": "openai", "input": 0.15, "output": 0.60, "tier": "fast"},
    # Mistral
    "mistral-large-latest": {"provider": "mistral", "input": 2.00, "output": 6.00, "tier": "premium"},
    "mistral-small-latest": {"provider": "mistral", "input": 0.10, "output": 0.30, "tier": "fast"},
}

# Which models to test per tier (keep cost reasonable)
TEST_MODELS = {
    "premium": ["claude-sonnet-4-6", "gpt-4o", "mistral-large-latest"],
    "fast": ["claude-haiku-4-5-20251001", "gpt-4o-mini", "mistral-small-latest"],
}


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = MODELS.get(model, {"input": 1.0, "output": 3.0})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


# ---------------------------------------------------------------------------
# API callers
# ---------------------------------------------------------------------------

def _call_anthropic(api_key: str, model: str, system: str, user: str, max_tokens: int = 1500) -> dict:
    body = json.dumps({
        "model": model, "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}]
    }).encode()
    req = Request("https://api.anthropic.com/v1/messages", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", "2023-06-01")
    start = time.time()
    resp = urlopen(req, timeout=60)
    latency = int((time.time() - start) * 1000)
    result = json.loads(resp.read().decode())
    usage = result.get("usage", {})
    return {
        "content": result["content"][0]["text"],
        "latency_ms": latency,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def _call_openai(api_key: str, model: str, system: str, user: str, max_tokens: int = 1500) -> dict:
    body = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.1,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]
    }).encode()
    req = Request("https://api.openai.com/v1/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    start = time.time()
    resp = urlopen(req, timeout=60)
    latency = int((time.time() - start) * 1000)
    result = json.loads(resp.read().decode())
    usage = result.get("usage", {})
    return {
        "content": result["choices"][0]["message"]["content"],
        "latency_ms": latency,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }


def _call_mistral(api_key: str, model: str, system: str, user: str, max_tokens: int = 1500) -> dict:
    body = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.1,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]
    }).encode()
    req = Request("https://api.mistral.ai/v1/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    start = time.time()
    resp = urlopen(req, timeout=60)
    latency = int((time.time() - start) * 1000)
    result = json.loads(resp.read().decode())
    usage = result.get("usage", {})
    return {
        "content": result["choices"][0]["message"]["content"],
        "latency_ms": latency,
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }


def call_model(model: str, system: str, user: str, keys: dict) -> dict:
    info = MODELS[model]
    provider = info["provider"]
    if provider == "anthropic":
        return _call_anthropic(keys["anthropic"], model, system, user)
    elif provider == "openai":
        return _call_openai(keys["openai"], model, system, user)
    elif provider == "mistral":
        return _call_mistral(keys["mistral"], model, system, user)


# ---------------------------------------------------------------------------
# Category tasks + scoring
# ---------------------------------------------------------------------------

CATEGORIES = {}


def category(name):
    def decorator(fn):
        CATEGORIES[name] = fn
        return fn
    return decorator


@category("1. Document Extraction")
def task_document_extraction(model, keys):
    system = "You are a financial document classifier. Return ONLY valid JSON."
    user = """Classify this document and extract fields with per-field confidence:

CAPITAL CALL NOTICE
Fund: Meridian Capital Partners III, L.P.
Call #: 14
Amount Due: USD 2,500,000
Due Date: 2026-05-15
Recipient: Meridian Family Office
Please remit by wire transfer to the account on file no later than the due date.

Return JSON: {"document_type": "...", "confidence": 0.0-1.0, "reasoning": "...", "fields": {"fund_name": {"value": "...", "confidence": 0.0-1.0}, "amount_due": {"value": "...", "confidence": ...}, "due_date": {"value": "...", "confidence": ...}, "recipient": {"value": "...", "confidence": ...}}}"""

    raw = call_model(model, system, user, keys)
    content = raw["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if content.startswith("json"):
            content = content[4:].strip()

    try:
        parsed = json.loads(content)
        fields = parsed.get("fields", parsed.get("extracted_fields", {}))
        correct = 0
        total = 4
        if "meridian" in str(fields.get("fund_name", {}).get("value", "")).lower(): correct += 1
        if "2,500,000" in str(fields.get("amount_due", {}).get("value", "")) or "2500000" in str(fields.get("amount_due", {}).get("value", "")): correct += 1
        if "2026-05-15" in str(fields.get("due_date", {}).get("value", "")) or "05-15" in str(fields.get("due_date", {}).get("value", "")): correct += 1
        if "meridian" in str(fields.get("recipient", fields.get("recipient_entity", {})).get("value", "")).lower(): correct += 1

        has_reasoning = len(parsed.get("reasoning", "")) > 20
        score = (correct / total * 80) + (20 if has_reasoning else 0)
    except:
        score = 0
    return score, raw


@category("2. Code Generation")
def task_code_generation(model, keys):
    system = "You are a senior Python developer. Write production-quality code."
    user = """Write a FastAPI endpoint that:
1. Accepts POST /packages/{id}/claim
2. Requires JWT authentication (use Depends(get_current_user))
3. Only allows users with role "reviewer"
4. Uses optimistic locking (version column) to prevent race conditions
5. Returns 409 if already claimed, 403 if wrong role, 404 if not found
6. Creates an audit trail entry

Return ONLY the Python code, no explanation."""

    raw = call_model(model, system, user, keys)
    content = raw["content"]

    score = 0
    checks = [
        ("@router.post" in content or "@app.post" in content, 15),
        ("get_current_user" in content or "current_user" in content, 10),
        ("reviewer" in content, 10),
        ("version" in content, 15),
        ("409" in content, 10),
        ("403" in content, 10),
        ("404" in content, 10),
        ("audit" in content.lower(), 10),
        ("async def" in content, 5),
        ("HTTPException" in content or "raise" in content, 5),
    ]
    for check, points in checks:
        if check: score += points

    return score, raw


@category("3. Code Validation")
def task_code_validation(model, keys):
    system = "You are a code reviewer. Find ALL bugs in the code."
    user = """Find every bug in this Python code:

```python
async def attest_package(pkg_id: str, body: AttestBody, db: AsyncSession, current_user: User):
    pkg = await db.execute(select(Package).where(Package.id == pkg_id))
    pkg = pkg.scalar_one_or_none()

    if pkg.state not in ("routed_for_approval", "exception_surfaced"):
        raise HTTPException(403, "Invalid state")

    action_name = "attested_decision" if body.action == "approved" else "attested_decision"

    pkg.state = "decision_recorded"
    await db.commit()

    audit = AuditEvent(package_id=pkg_id, actor_user_id=current_user.id,
                       action=action_name, after_state={"status": pkg.state})
    db.add(audit)
    await db.commit()
```

List each bug with line number and fix. Be exhaustive."""

    raw = call_model(model, system, user, keys)
    content = raw["content"].lower()

    known_bugs = [
        ("action_name" in content and ("tautolog" in content or "same" in content or "identical" in content or "both branches" in content), 25),
        ("null" in content or "none" in content or "404" in content, 15),  # missing 404 check
        ("role" in content or "permission" in content or "403" in content, 15),  # no role check
        ("commit" in content and ("before" in content or "after" in content or "order" in content or "audit" in content), 15),  # commit before audit
        ("state_machine" in content or "bypass" in content or "transition" in content or "validate" in content, 15),  # bypasses state machine
        ("version" in content or "optimistic" in content or "concurren" in content or "race" in content, 15),  # no optimistic lock
    ]
    score = 0
    for check, points in known_bugs:
        if check: score += points
    return min(score, 100), raw


@category("4. Test Writing")
def task_test_writing(model, keys):
    system = "You are a test engineer. Write comprehensive pytest tests."
    user = """Write pytest tests for this function signature:

```python
def validate_transition(current_state: str, next_state: str, actor_role: str) -> None:
    '''Validates a package state transition. Raises InvalidTransition if not allowed.
    States: submitted, intake_complete, under_review, routed_for_approval, decision_recorded, exception_surfaced
    Roles: admin, reviewer, approver
    Rules: only reviewer can transition under_review -> routed_for_approval
           only approver can transition routed_for_approval -> decision_recorded
           decision_recorded is terminal (no transitions out)
    '''
```

Write at least 8 tests covering happy paths, invalid transitions, role restrictions, and terminal state. Use parametrize where appropriate."""

    raw = call_model(model, system, user, keys)
    content = raw["content"]

    score = 0
    checks = [
        ("def test_" in content, 10),
        (content.count("def test_") >= 4, 10),
        (content.count("def test_") >= 8, 10),
        ("parametrize" in content or "parametrise" in content, 10),
        ("InvalidTransition" in content or "raises" in content, 10),
        ("decision_recorded" in content, 10),
        ("reviewer" in content, 10),
        ("approver" in content, 10),
        ("routed_for_approval" in content, 10),
        ("terminal" in content.lower() or "cannot" in content.lower() or "not allowed" in content.lower(), 10),
    ]
    for check, points in checks:
        if check: score += points
    return score, raw


@category("5. Logic / Reasoning")
def task_logic_reasoning(model, keys):
    system = "You are analyzing a state machine for correctness."
    user = """A capital call package has 6 states and these transitions:
- submitted -> intake_complete (system, after classification)
- intake_complete -> under_review (reviewer claims)
- intake_complete -> exception_surfaced (system, if confidence < 0.5)
- under_review -> routed_for_approval (reviewer routes)
- under_review -> intake_complete (reviewer releases claim)
- routed_for_approval -> decision_recorded (approver attests)
- routed_for_approval -> under_review (approver returns to reviewer)
- exception_surfaced -> under_review (reviewer resolves)
- decision_recorded -> (terminal, no outbound transitions)

Questions:
1. Can a package go from submitted directly to decision_recorded? Why?
2. What happens if two reviewers try to claim the same package simultaneously?
3. If an approver rejects, what state should the package go to?
4. Is there a path from exception_surfaced to decision_recorded? Trace it.
5. What's missing from this state machine that a real capital call workflow would need?

Answer each precisely."""

    raw = call_model(model, system, user, keys)
    content = raw["content"].lower()

    score = 0
    checks = [
        ("no" in content[:500] or "cannot" in content[:500], 20),  # Q1: no direct path
        ("race" in content or "concurren" in content or "optimistic" in content or "lock" in content, 20),  # Q2: concurrency
        ("under_review" in content and ("reject" in content or "return" in content), 20),  # Q3: return to review
        ("exception" in content and "under_review" in content and "routed" in content and "decision" in content, 20),  # Q4: trace the path
        (any(w in content for w in ["expir", "timeout", "escalat", "cancel", "archive", "void", "amend"]), 20),  # Q5: what's missing
    ]
    for check, points in checks:
        if check: score += points
    return score, raw


@category("6. Product Management")
def task_product_management(model, keys):
    system = "You are a product manager writing acceptance criteria for a financial workflow application."
    user = """Write acceptance criteria (Gherkin-style Given/When/Then) for this user story:

"As a family office approver, I want to formally attest my approval decision on a capital call package so that the decision is traceable, timestamped, and recorded against my identity."

Requirements:
- The attestation must show what the AI extracted and its confidence
- The attestation must show any reviewer notes
- The approval is a formal moment, not a casual button click
- The decision must be recorded in an immutable audit trail
- The approver should see what they're confirming before they confirm it

Write at least 6 acceptance criteria. Be specific about edge cases."""

    raw = call_model(model, system, user, keys)
    content = raw["content"]

    score = 0
    checks = [
        ("given" in content.lower() and "when" in content.lower() and "then" in content.lower(), 15),
        (content.lower().count("given") >= 4, 10),
        ("confidence" in content.lower(), 10),
        ("reviewer" in content.lower() and "note" in content.lower(), 10),
        ("audit" in content.lower() or "trail" in content.lower() or "immutable" in content.lower(), 10),
        ("timestamp" in content.lower() or "recorded" in content.lower(), 10),
        ("identity" in content.lower() or "actor" in content.lower() or "name" in content.lower(), 10),
        ("confirm" in content.lower() or "attestation" in content.lower(), 10),
        (any(w in content.lower() for w in ["edge", "error", "fail", "invalid", "cancel", "timeout", "already"]), 10),
        (len(content) > 500, 5),
    ]
    for check, points in checks:
        if check: score += points
    return score, raw


@category("7. UX Design Critique")
def task_ux_design(model, keys):
    system = "You are a senior UX designer for premium private financial applications."
    user = """Critique this UI description for a capital call approval page and suggest improvements:

Current design:
- Page title: "Document Details"
- Status: green badge saying "Approved"
- File info: filename, size, upload date
- Classification: "capital_call_notice" with "99%" next to it
- Two buttons at the bottom: "Approve" (green) and "Reject" (red)
- Small text link "View audit log" at the very bottom

The app is for a family office reviewing multi-million dollar capital calls. It should feel like boutique private banking software, not a generic admin dashboard.

Provide:
1. What's wrong with the current design (at least 5 issues)
2. How each should be fixed
3. What language/copy changes are needed
4. What the visual hierarchy should be
5. How AI confidence should be surfaced"""

    raw = call_model(model, system, user, keys)
    content = raw["content"].lower()

    score = 0
    checks = [
        (any(w in content for w in ["generic", "admin", "saas", "utilitarian"]), 15),  # identifies the problem
        (any(w in content for w in ["attest", "formal", "ceremony", "deliberate", "moment"]), 15),  # understands attestation
        (any(w in content for w in ["private", "boutique", "premium", "editorial"]), 10),  # knows the target aesthetic
        ("confidence" in content and ("per-field" in content or "each field" in content or "individual" in content), 10),
        ("audit" in content and ("first-class" in content or "prominent" in content or "visible" in content or "not hidden" in content), 10),
        (any(w in content for w in ["cormorant", "serif", "typograph", "font"]), 10),  # typography awareness
        (content.count("\n") > 15, 10),  # thorough response
        ("hierarchy" in content, 10),  # information hierarchy
        (any(w in content for w in ["approve", "language", "copy", "wording", "label"]), 5),
        (len(content) > 800, 5),
    ]
    for check, points in checks:
        if check: score += points
    return score, raw


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_scorecard(keys: dict, tier: str = "all"):
    tiers = ["fast", "premium"] if tier == "all" else [tier]
    models_to_test = []
    for t in tiers:
        for m in TEST_MODELS[t]:
            if MODELS[m]["provider"] in keys and keys[MODELS[m]["provider"]]:
                models_to_test.append(m)

    print(f"\n{'='*100}")
    print(f"ARUKAI MODEL SCORECARD — {len(models_to_test)} models × {len(CATEGORIES)} categories")
    print(f"{'='*100}\n")

    results = {}
    for model in models_to_test:
        results[model] = {}
        info = MODELS[model]
        print(f"\n--- {model} ({info['provider']}, {info['tier']}) ---")

        for cat_name, task_fn in CATEGORIES.items():
            print(f"  {cat_name}...", end=" ", flush=True)
            try:
                score, raw = task_fn(model, keys)
                cost = _calc_cost(model, raw["input_tokens"], raw["output_tokens"])
                results[model][cat_name] = {
                    "score": score,
                    "latency_ms": raw["latency_ms"],
                    "cost_usd": cost,
                    "input_tokens": raw["input_tokens"],
                    "output_tokens": raw["output_tokens"],
                }
                print(f"{score}/100, {raw['latency_ms']}ms, ${cost:.5f}")
            except Exception as e:
                results[model][cat_name] = {"score": 0, "latency_ms": 0, "cost_usd": 0, "error": str(e)}
                print(f"ERROR: {e}")
            time.sleep(0.3)

    # Print scorecard table
    print(f"\n\n{'='*130}")
    print("SCORECARD TABLE")
    print(f"{'='*130}")

    cat_names = list(CATEGORIES.keys())
    short_cats = ["DocExtract", "CodeGen", "CodeValid", "Testing", "Logic", "ProdMgmt", "UXDesign"]

    header = f"{'Model':<32} {'Tier':<8} "
    for sc in short_cats:
        header += f"{'|'+sc:>11}"
    header += f" {'| AVG':>7} {'| Cost':>9} {'| Latency':>10}"
    print(header)
    print("-" * 130)

    scorecard_rows = []
    for model in models_to_test:
        info = MODELS[model]
        row = f"{model:<32} {info['tier']:<8} "
        scores = []
        total_cost = 0
        total_latency = 0

        for cat_name, short in zip(cat_names, short_cats):
            r = results[model].get(cat_name, {})
            s = r.get("score", 0)
            scores.append(s)
            total_cost += r.get("cost_usd", 0)
            total_latency += r.get("latency_ms", 0)
            row += f"|{s:>8}/100"

        avg = sum(scores) / len(scores) if scores else 0
        row += f" |{avg:>5.0f}  ${total_cost:>7.4f}  {total_latency:>7.0f}ms"
        print(row)

        scorecard_rows.append({
            "model": model,
            "provider": info["provider"],
            "tier": info["tier"],
            "scores": dict(zip(short_cats, scores)),
            "average": avg,
            "total_cost": total_cost,
            "total_latency_ms": total_latency,
        })

    # Best per category
    print(f"\n\nBEST PER CATEGORY:")
    for cat_name, short in zip(cat_names, short_cats):
        best_model = max(models_to_test, key=lambda m: results[m].get(cat_name, {}).get("score", 0))
        best_score = results[best_model].get(cat_name, {}).get("score", 0)
        print(f"  {short:<12} → {best_model} ({best_score}/100)")

    # Cost-efficiency ranking
    print(f"\n\nCOST-EFFICIENCY (avg score / total cost):")
    for row in sorted(scorecard_rows, key=lambda r: r["average"] / max(r["total_cost"], 0.00001), reverse=True):
        efficiency = row["average"] / max(row["total_cost"], 0.00001)
        print(f"  {row['model']:<32} avg={row['average']:.0f}, cost=${row['total_cost']:.4f}, efficiency={efficiency:.0f}")

    # Recommendation
    print(f"\n\nRECOMMENDATION BY USE CASE:")
    fast_models = [r for r in scorecard_rows if r["tier"] == "fast"]
    premium_models = [r for r in scorecard_rows if r["tier"] == "premium"]

    if fast_models:
        best_fast = max(fast_models, key=lambda r: r["average"])
        cheapest_fast = min(fast_models, key=lambda r: r["total_cost"])
        print(f"  Fast/cheap (extraction, formatting): {cheapest_fast['model']} (${cheapest_fast['total_cost']:.4f})")
        print(f"  Best quality fast: {best_fast['model']} (avg {best_fast['average']:.0f})")

    if premium_models:
        best_premium = max(premium_models, key=lambda r: r["average"])
        print(f"  Premium (architecture, proof): {best_premium['model']} (avg {best_premium['average']:.0f})")

    # Save
    output = Path("model_scorecard_results.json")
    with open(output, "w") as f:
        json.dump({"scorecard": scorecard_rows, "detailed": {k: v for k, v in results.items()}}, f, indent=2, default=str)
    print(f"\n\nFull results saved to: {output}")
    print("=" * 130)


def main():
    parser = argparse.ArgumentParser(description="Arukai Model Scorecard")
    parser.add_argument("--anthropic-key", default=os.environ.get("ANTHROPIC_API_KEY", ""))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--mistral-key", default=os.environ.get("MISTRAL_API_KEY", ""))
    parser.add_argument("--tier", default="all", choices=["fast", "premium", "all"])
    args = parser.parse_args()

    keys = {
        "anthropic": args.anthropic_key,
        "openai": args.openai_key,
        "mistral": args.mistral_key,
    }

    run_scorecard(keys, args.tier)


if __name__ == "__main__":
    main()

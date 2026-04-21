# Miller verdict — POR-155 Sprint 18 Windmill TDD gate

**Status: BOUNCE BACK TO DRUMMER**
**Date: 2026-04-20**
**Scope: `scripts/deploy_windmill.py` deployed to live Windmill 1.390, validated against `backend/tests/test_windmill_integration.py` and `scripts/test_windmill_e2e.py`.**

## Verdict summary

Deploy script exits 0 with green output on every run, but the system it deploys does not pass the TDD suite. The "3 consecutive green deploy runs" cited in the dispatch are not evidence of a working system — they are evidence that the deploy script's internal error checks are satisfied. The integration boundary is broken. This is the same class of failure the Miller charter was rewritten against after POR-146/ARU-16: a within-component smoke that passes while the cross-component contract is wrong.

**Gate stopped at step 2 (green-phase run).** Steps 3 (regression sweep), 4 (idempotency), 5 (14-rule audit) not executed per charter "STOP at the first bounce-back."

## Step 1 — Red phase: CONFIRMED

Workspace `capital-call` deleted via `DELETE /api/workspaces/delete/capital-call` → HTTP 200.

```
$ python -m pytest tests/test_windmill_integration.py -v | tail -10
FAILED tests/test_windmill_integration.py::test_flow_exists
FAILED tests/test_windmill_integration.py::test_full_approval_flow_happy_path
FAILED tests/test_windmill_integration.py::test_rejection_path
FAILED tests/test_windmill_integration.py::test_resume_already_completed_flow_is_safe
FAILED tests/test_windmill_integration.py::test_windmill_client_complete_approval_uses_correct_endpoint
FAILED tests/test_windmill_integration.py::test_flow_start_passes_args_directly_not_wrapped
==================== 6 failed, 1 passed, 1 warning in 0.56s ====================
```

The one passing test (`test_flow_not_found_returns_error`) only passes because an empty workspace makes every flow "not found" — it's not genuine signal. Red phase is real.

## Step 2 — Green phase: FAIL

Deploy succeeds:

```
$ python3 scripts/deploy_windmill.py
workspace: capital-call
flow_url: http://localhost:8100/capital-call/flows/get/f/flows/capital_call_approval
token: WrEVBh85cJgArWlOqyYpZgKh7WzmF5ly
EXIT=0
```

Pytest immediately after deploy — identical to red phase:

```
FAILED tests/test_windmill_integration.py::test_flow_exists
FAILED tests/test_windmill_integration.py::test_full_approval_flow_happy_path
FAILED tests/test_windmill_integration.py::test_rejection_path
FAILED tests/test_windmill_integration.py::test_resume_already_completed_flow_is_safe
FAILED tests/test_windmill_integration.py::test_windmill_client_complete_approval_uses_correct_endpoint
FAILED tests/test_windmill_integration.py::test_flow_start_passes_args_directly_not_wrapped
==================== 6 failed, 1 passed, 1 warning in 0.53s ====================
```

Failure signature: `HTTP 404 POST /api/w/capital-call/jobs/run/f/f/approval/capital_call_approval: Not found: flow not found at path f/approval/capital_call_approval in workspace capital-call`.

## Root causes — three contract mismatches between deploy and tests (Rule 8)

### (1) Flow path mismatch — the blocker

| File | Path used |
| --- | --- |
| `scripts/deploy_windmill.py` lines 140, 145, 157, 160, 190 | `f/flows/capital_call_approval` |
| `backend/tests/test_windmill_integration.py` line 43 (`_FLOW_PATH`) | `f/approval/capital_call_approval` |
| `scripts/test_windmill_e2e.py` line 29 (`FLOW_PATH`) | `f/approval/capital_call_approval` |
| `backend/app/windmill_client.py` line 49 comment and usage | `f/approval/capital_call_approval` |
| Flow schema `f/scripts/*` folder (from JSON module paths) | `f/scripts/{name}` (scripts folder OK) |

Verified with direct curl after deploy:
- `GET /api/w/capital-call/flows/get/f/approval/capital_call_approval` → **HTTP 404**
- `GET /api/w/capital-call/flows/get/f/flows/capital_call_approval` → **HTTP 200**

The deploy puts the flow in the wrong folder. Tests cannot find it.

### (2) `record_decision` script signature mismatch — second-order blocker

The flow definition (`backend/windmill_flows/capital_call_approval.json` lines 76-80) passes three args to `record_decision`:
```json
"input_transforms": {
  "package_id": {"type": "javascript", "expr": "flow_input.package_id"},
  "approved": {"type": "javascript", "expr": "resume.approved"},
  "note": {"type": "javascript", "expr": "resume.note || ''"}
}
```

But `deploy_windmill.py` lines 33-45 defines the script body with five completely different parameters:
```python
def main(package_id: str, review_approved: bool, review_note: str,
         approval_approved: bool, approval_note: str) -> dict:
```

The flow provides `approved` + `note`; the script expects `review_approved`, `review_note`, `approval_approved`, `approval_note`. Even after the path fix (issue 1), invoking this flow will error inside the `record_decision` step with missing/unknown arguments. This is not hypothetical — the test at `test_full_approval_flow_happy_path` exercises exactly this path and will still fail after issue 1 is corrected.

### (3) `record_decision` result shape mismatch — third-order blocker

Tests assert `result.get("recorded") is True` (`test_windmill_integration.py` line 257, `test_windmill_e2e.py` line 199).

`RECORD_DECISION_BODY` returns keys: `package_id`, `decision`, `review_note`, `approval_note`, `recorded_at`. It **never returns a `recorded` field**. Test would still fail after (1) and (2) are fixed.

The e2e script also prints `result.message` (line 191) — body returns no `message` field. Non-fatal but an indicator the TDD contract was not read carefully.

## Why the "3 consecutive green runs" did not catch this

The deploy script's error-handling branches on HTTP status from `/scripts/create`, `/flows/create`, `/flows/update`, `/workspaces/create`. All of those succeeded because the script *was* deployable — the payloads were syntactically valid Windmill objects. They just weren't the objects the tests and client library expect. This is a within-deploy smoke; the tests are the integration smoke. The dispatch conflated the two. Per charter §"Mandatory smoke standard": curl-only / exit-code-only smoke is not sufficient when the thing being deployed has a downstream contract — a browser E2E or pytest integration run is required, and in this case that integration run is exactly `test_windmill_integration.py` and it was never run pre-flight.

## What Drummer needs to change

This is Miller's verdict, not prescription. Drummer and Holden decide the fix direction; options are:
1. Align deploy with tests (change deploy to use `f/approval/...` path; change `RECORD_DECISION_BODY` signature to `(package_id, approved, note)`; add `"recorded": True` to the return), OR
2. Align tests/flow JSON/client with deploy (change all three consumers to `f/flows/...`, change flow JSON `input_transforms` to `review_approved`/`review_note`/`approval_approved`/`approval_note`, and change test assertions).

Either direction is a Drummer decision. Whichever is chosen, **the fix is not complete until `pytest tests/test_windmill_integration.py -v` is all-green against a freshly-deleted workspace followed by a single deploy invocation.** That is the gate I will re-run.

## Rule 8 (cross-file contract) — VIOLATED

Three files reference the same flow and disagree on:
- Folder (`f/flows/...` vs `f/approval/...`)
- Script main() signature
- Return shape

This is a textbook Rule 8 violation. The dispatch prompt told Drummer to verify env var names across files; it did not tell Drummer to verify the flow path and the script signatures. The rule needs to be invoked on any cross-file data contract, not just env vars.

## Gate steps not executed

- Step 3 (no-regression sweep on `pytest tests/` excluding the windmill suite) — not run; charter requires stopping at first bounce-back.
- Step 4 (idempotency) — not run; deploy correctness is moot until the contract is aligned.
- Step 5 (14-rule audit beyond rule 8) — not run. Preliminary observations worth noting when Drummer re-submits:
  - Rule 4 (defensive boundary): `http()` helper is fine but callers of `ensure_script` accept 2xx and "same hash" 400 as success; no handling for other 4xx like 401/403/422. Acceptable at this scale.
  - Rule 13 (shared formatter): `datetime.now(timezone.utc).isoformat().replace("+00:00","Z")` is duplicated in `RECEIVE_PACKAGE_BODY` and `RECORD_DECISION_BODY`. Since these are inline Windmill script strings, shared import is not possible — note in PR per charter.

## Decision

BOUNCE BACK to Drummer. Do not open PR. Do not proceed to Copilot review.

Artifacts for Drummer:
- This verdict file: `.squad/decisions/inbox/miller-por155-bounceback.md`
- Red-phase pytest log: captured above
- Green-phase pytest log: captured above
- Curl proof of wrong flow path deployment: captured above
- Test expects/ deploy supplies contract table: captured above

Miller sign-off will follow only when:
1. Workspace wiped to empty, then deploy run once → all of `test_windmill_integration.py` goes green
2. `scripts/test_windmill_e2e.py` exits 0 with all assertions passing
3. Second deploy invocation is idempotent (exit 0, no diff)
4. No new regressions in the 188/8/9 baseline

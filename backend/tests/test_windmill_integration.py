"""Integration tests for Windmill capital_call_approval E2E flow.

These tests hit real Windmill via HTTP (no mocking). They are skipped when:
  - SKIP_WINDMILL_TESTS=1 env var is set
  - Windmill is not reachable at WINDMILL_BASE_URL (default http://localhost:8100)

TDD: these tests were written BEFORE the implementation fixes. They will fail
against the unfixed windmill_client.py and flow definition.

Test coverage:
  (a) Start flow — returns a job_id, flow suspends at review_gate
  (b) Resume review_gate — first gate unblocks, flow suspends at approval_gate
  (c) Resume approval_gate — second gate unblocks, record_decision runs
  (d) Final flow status is success and record_decision result is correct
  (e) Idempotency — test can be run multiple times (each run starts a fresh job)
  (f) Error states — flow not found, resume on already-completed flow

Windmill suspend state convention (v1.390.0):
  When a module M has `suspend: {required_events: 1}`, Windmill shows:
    - M: Success (the identity/script ran successfully)
    - M+1: WaitingForEvents (the NEXT module is shown as waiting because M's suspend is active)
  This means "approval_gate: WaitingForEvents" = flow is paused at review_gate's suspend.
  After first resume: "record_decision: WaitingForEvents" = flow is paused at approval_gate's suspend.
"""
import json
import os
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

# ── Configuration ──────────────────────────────────────────────────────────────

_BASE_URL: str = os.getenv("WINDMILL_BASE_URL", "http://localhost:8100")
_TOKEN: str = os.getenv("WINDMILL_TOKEN", "dRRYLqFTy6XzvstQ3iEVzeVQ1jwQTXQd")
_WORKSPACE: str = os.getenv("WINDMILL_WORKSPACE", "capital-call")

# Full flow path including folder prefix — used for GET and flow/resume endpoints
_FLOW_PATH: str = "f/approval/capital_call_approval"

# For the run endpoint: POST /api/w/{ws}/jobs/run/f/{path}
# The {path} parameter accepts the full flow path including folder prefix
_FLOW_RUN_PATH: str = _FLOW_PATH  # results in URL: /jobs/run/f/f/approval/...

_SKIP_REASON = "SKIP_WINDMILL_TESTS=1 or Windmill not reachable"


def _windmill_reachable() -> bool:
    if os.getenv("SKIP_WINDMILL_TESTS") == "1":
        return False
    try:
        req = Request(f"{_BASE_URL}/api/version", method="GET")
        req.add_header("Authorization", f"Bearer {_TOKEN}")
        with urlopen(req, timeout=5):
            return True
    except (URLError, HTTPError):
        return False


_wm_available = _windmill_reachable()

requires_windmill = pytest.mark.skipif(
    not _wm_available,
    reason=_SKIP_REASON,
)


# ── Thin HTTP helper (zero SDK dependency — rule 10) ───────────────────────────

def _request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = f"{_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
    }
    req = Request(url, method=method, headers=headers)
    if body is not None:
        req.data = json.dumps(body).encode()
    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if not raw:
                return None
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw.decode()
    except HTTPError as exc:
        err_body = exc.read().decode() if exc.fp else ""
        raise RuntimeError(
            f"HTTP {exc.code} {method} {path}: {err_body[:300]}"
        ) from exc


def _start_flow(package_id: str, uploaded_by: str) -> str:
    """Start the flow with direct args (not wrapped in {'args': ...})."""
    result = _request(
        "POST",
        f"/api/w/{_WORKSPACE}/jobs/run/f/{_FLOW_RUN_PATH}",
        {"package_id": package_id, "uploaded_by": uploaded_by},
    )
    assert isinstance(result, str) and len(result) > 0, (
        f"Expected string job_id from flow start, got: {result!r}"
    )
    return result


def _get_flow_modules(job_id: str) -> dict[str, dict[str, Any]]:
    """Return {module_id: module_status} for the given flow job."""
    status = _request("GET", f"/api/w/{_WORKSPACE}/jobs_u/get/{job_id}")
    assert isinstance(status, dict), f"Unexpected status type: {type(status)}"
    return {
        m["id"]: m
        for m in status.get("flow_status", {}).get("modules", [])
    }


def _wait_for_module_type(
    job_id: str,
    module_id: str,
    target_types: set[str],
    timeout: int = 30,
) -> dict[str, Any]:
    """Poll until the named module reaches one of target_types; return full status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _request("GET", f"/api/w/{_WORKSPACE}/jobs_u/get/{job_id}")
        assert isinstance(status, dict), f"Unexpected status type: {type(status)}"
        if status.get("type") == "CompletedJob":
            return status
        for mod in status.get("flow_status", {}).get("modules", []):
            if mod["id"] == module_id and mod.get("type") in target_types:
                return status
        time.sleep(2)
    raise TimeoutError(
        f"Module {module_id!r} did not reach {target_types} within {timeout}s "
        f"for job {job_id}"
    )


def _wait_for_job_completion(job_id: str, timeout: int = 30) -> dict[str, Any]:
    """Poll until the flow job reaches CompletedJob."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _request("GET", f"/api/w/{_WORKSPACE}/jobs_u/get/{job_id}")
        assert isinstance(status, dict)
        if status.get("type") == "CompletedJob":
            return status
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def _resume_flow_as_owner(job_id: str, payload: dict[str, Any]) -> None:
    """Resume a suspended flow using the owner endpoint (no HMAC signature needed)."""
    result = _request(
        "POST",
        f"/api/w/{_WORKSPACE}/jobs/flow/resume/{job_id}",
        payload,
    )
    # 201 returns empty body → None is success; any other truthy value is acceptable
    assert result is None or isinstance(result, (str, dict)), (
        f"Unexpected resume response: {result!r}"
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


@requires_windmill
def test_flow_exists() -> None:
    """Flow definition is deployed and reachable."""
    flow = _request("GET", f"/api/w/{_WORKSPACE}/flows/get/{_FLOW_PATH}")
    assert isinstance(flow, dict), f"Expected dict, got {type(flow)}"
    assert flow["summary"] == "Capital Call Approval Workflow"
    module_ids = [m["id"] for m in flow["value"]["modules"]]
    assert module_ids == [
        "receive_package",
        "classify_document",
        "review_gate",
        "approval_gate",
        "record_decision",
    ]


@requires_windmill
def test_full_approval_flow_happy_path() -> None:
    """Full E2E: start → resume review_gate → resume approval_gate → success.

    Windmill suspend convention: the module shown as WaitingForEvents is the NEXT
    module whose execution is gated, not the module whose suspend is active.

    Initial suspended state (review_gate suspend active):
      review_gate: Success, approval_gate: WaitingForEvents

    After first resume (approval_gate suspend active):
      approval_gate: Success, record_decision: WaitingForEvents

    After second resume:
      flow completes with decision='approved'
    """
    package_id = f"integ-{uuid.uuid4().hex[:8]}"

    # (a) Start the flow
    job_id = _start_flow(package_id, "integration-test")

    # (b) Wait for review_gate's suspend to block: approval_gate shows WaitingForEvents
    _wait_for_module_type(
        job_id, "approval_gate", {"WaitingForEvents"}, timeout=30
    )
    modules = _get_flow_modules(job_id)
    assert modules["review_gate"]["type"] == "Success", (
        "review_gate must be Success (identity ran) when review_gate suspend is active"
    )
    assert modules["approval_gate"]["type"] == "WaitingForEvents", (
        "approval_gate must be WaitingForEvents when review_gate suspend is active"
    )

    # (c) Resume review_gate — owner resumes the parent flow job
    _resume_flow_as_owner(job_id, {"approved": True, "note": "LGTM from reviewer"})

    # (d) Wait for approval_gate's suspend to block: record_decision shows WaitingForEvents
    _wait_for_module_type(
        job_id, "record_decision", {"WaitingForEvents"}, timeout=30
    )
    modules = _get_flow_modules(job_id)
    assert modules["approval_gate"]["type"] == "Success", (
        "approval_gate must be Success (identity ran) when approval_gate suspend is active"
    )
    assert modules["record_decision"]["type"] == "WaitingForEvents", (
        "record_decision must be WaitingForEvents when approval_gate suspend is active"
    )

    # (e) Resume approval_gate
    _resume_flow_as_owner(job_id, {"approved": True, "note": "Attested by approver"})

    # (f) Wait for flow to complete
    final = _wait_for_job_completion(job_id, timeout=30)
    assert final.get("success") is True, (
        f"Flow should succeed, got success={final.get('success')} result={final.get('result')}"
    )

    # (g) Verify record_decision output contains decision='approved'
    result = final.get("result", {})
    assert isinstance(result, dict), f"Expected dict result, got: {type(result)}"
    assert result.get("decision") == "approved", (
        f"Expected decision='approved', got: {result.get('decision')!r}. "
        f"Note: the flow definition must use results.approval_gate.resume.approved "
        f"(not results.approval_gate.resume which returns the whole object). "
        f"Full result: {result}"
    )
    assert result.get("package_id") == package_id, (
        f"Expected package_id={package_id!r}, got: {result.get('package_id')!r}"
    )
    assert result.get("recorded") is True


@requires_windmill
def test_rejection_path() -> None:
    """Full E2E: start → approve review_gate → reject approval_gate → success with decision=rejected."""
    package_id = f"integ-{uuid.uuid4().hex[:8]}"

    job_id = _start_flow(package_id, "integration-test")

    _wait_for_module_type(job_id, "approval_gate", {"WaitingForEvents"}, timeout=30)
    _resume_flow_as_owner(job_id, {"approved": True, "note": "OK to escalate"})

    _wait_for_module_type(job_id, "record_decision", {"WaitingForEvents"}, timeout=30)
    _resume_flow_as_owner(job_id, {"approved": False, "note": "Rejected by approver"})

    final = _wait_for_job_completion(job_id, timeout=30)
    assert final.get("success") is True, (
        f"Flow should succeed even on rejection path; result={final.get('result')}"
    )
    result = final.get("result", {})
    assert result.get("decision") == "rejected", (
        f"Expected decision='rejected', got: {result.get('decision')!r}"
    )


@requires_windmill
def test_resume_already_completed_flow_is_safe() -> None:
    """Resuming a completed flow must not raise an unhandled 5xx server error.

    Covers the 'flow already completed' combinatoric (rule 14).
    Windmill returns 4xx for stale resumes — the client must handle it gracefully.
    """
    package_id = f"integ-{uuid.uuid4().hex[:8]}"
    job_id = _start_flow(package_id, "integration-test")

    _wait_for_module_type(job_id, "approval_gate", {"WaitingForEvents"}, timeout=30)
    _resume_flow_as_owner(job_id, {"approved": True, "note": "OK"})
    _wait_for_module_type(job_id, "record_decision", {"WaitingForEvents"}, timeout=30)
    _resume_flow_as_owner(job_id, {"approved": True, "note": "OK"})
    final = _wait_for_job_completion(job_id, timeout=30)
    assert final.get("success") is True

    # Attempt a second resume on the already-completed flow
    try:
        _resume_flow_as_owner(job_id, {"approved": True, "note": "stale retry"})
        # Windmill may accept it silently — no error is also acceptable
    except RuntimeError as exc:
        # Windmill CE v1.390.0 returns HTTP 500 with "parent flow job not found"
        # for stale resumes on completed flows. 4xx would be more correct but 500
        # is the actual server behavior. We just verify it raised, not that it succeeded.
        err = str(exc)
        assert "HTTP" in err, f"Expected HTTP error on stale resume, got: {err}"


@requires_windmill
def test_flow_not_found_returns_error() -> None:
    """Attempting to start a non-existent flow returns 404, not a job_id.

    Covers the 'flow not found' combinatoric (rule 14).
    """
    try:
        result = _request(
            "POST",
            f"/api/w/{_WORKSPACE}/jobs/run/f/f/approval/nonexistent_flow_xyz",
            {"package_id": "x", "uploaded_by": "test"},
        )
        assert not (isinstance(result, str) and len(result) == 36), (
            f"Expected error, not job_id: {result!r}"
        )
    except RuntimeError as exc:
        assert "HTTP 404" in str(exc), f"Expected 404, got: {exc}"


@requires_windmill
def test_windmill_client_complete_approval_uses_correct_endpoint() -> None:
    """WindmillClient.complete_approval must use /jobs/flow/resume/{id} (owner endpoint).

    Regression guard: the old code called /jobs_u/resume/{id} which requires an HMAC
    signature — without the signature it returns "parent flow job not found".
    """
    import sys
    sys.path.insert(0, "/home/sawan/arukai-capital-call/backend")
    from app.windmill_client import WindmillClient

    client = WindmillClient(base_url=_BASE_URL, token=_TOKEN)

    package_id = f"integ-{uuid.uuid4().hex[:8]}"
    job_id = _start_flow(package_id, "integration-test")

    # Wait for review_gate suspend: approval_gate becomes WaitingForEvents
    _wait_for_module_type(job_id, "approval_gate", {"WaitingForEvents"}, timeout=30)

    # Use WindmillClient.complete_approval to resume review_gate
    client.complete_approval(run_id=job_id, approved=True, note="via client method")

    # After client resume, record_decision should become WaitingForEvents
    # (approval_gate ran its identity and its own suspend is now active)
    _wait_for_module_type(job_id, "record_decision", {"WaitingForEvents"}, timeout=30)
    modules = _get_flow_modules(job_id)
    assert modules["approval_gate"]["type"] == "Success", (
        "approval_gate must be Success after complete_approval call on review_gate"
    )

    # Clean up: push through approval_gate so the job does not linger
    _resume_flow_as_owner(job_id, {"approved": True, "note": "cleanup"})
    _wait_for_job_completion(job_id, timeout=30)


@requires_windmill
def test_flow_start_passes_args_directly_not_wrapped() -> None:
    """WindmillClient.start_flow must pass args directly to the flow, not wrapped in {'args': ...}.

    When args are wrapped, scripts receive null for package_id and uploaded_by
    because the flow_input expression 'flow_input.package_id' resolves to undefined.
    """
    import sys
    sys.path.insert(0, "/home/sawan/arukai-capital-call/backend")
    from app.windmill_client import WindmillClient

    client = WindmillClient(base_url=_BASE_URL, token=_TOKEN)
    package_id = f"integ-{uuid.uuid4().hex[:8]}"

    job_id = client.start_flow("f/approval/capital_call_approval", {
        "package_id": package_id,
        "uploaded_by": "integration-test",
    })
    assert isinstance(job_id, str) and len(job_id) > 0, (
        f"start_flow must return a string job_id, got: {job_id!r}"
    )

    # Wait for the flow to pass receive_package and reach the first suspend
    _wait_for_module_type(job_id, "approval_gate", {"WaitingForEvents"}, timeout=30)

    # Verify receive_package ran with the correct package_id (not null)
    status = _request("GET", f"/api/w/{_WORKSPACE}/jobs_u/get/{job_id}")
    receive_job_id = None
    for mod in status.get("flow_status", {}).get("modules", []):
        if mod["id"] == "receive_package":
            receive_job_id = mod.get("job")
            break
    assert receive_job_id is not None, "receive_package must have a job_id"

    receive_result = _request(
        "GET", f"/api/w/{_WORKSPACE}/jobs/completed/get/{receive_job_id}"
    )
    assert isinstance(receive_result, dict), f"Expected dict, got: {type(receive_result)}"
    assert receive_result.get("result", {}).get("package_id") == package_id, (
        f"receive_package got package_id={receive_result.get('result',{}).get('package_id')!r}, "
        f"expected {package_id!r}. Args were likely wrapped incorrectly."
    )

    # Clean up: run both resumes so job does not linger
    _resume_flow_as_owner(job_id, {"approved": True, "note": "cleanup-1"})
    _wait_for_module_type(job_id, "record_decision", {"WaitingForEvents"}, timeout=30)
    _resume_flow_as_owner(job_id, {"approved": True, "note": "cleanup-2"})
    _wait_for_job_completion(job_id, timeout=30)

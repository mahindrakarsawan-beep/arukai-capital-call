"""E2E test: Windmill capital call approval workflow — full two-gate path.

Exercises the complete lifecycle against a running Windmill instance:
  0. Verify Windmill is up
  1. Verify flow is deployed
  2. Start flow with a test package
  3. Wait for review_gate suspend (approval_gate shows WaitingForEvents)
  4. Resume review_gate via owner endpoint
  5. Wait for approval_gate suspend (record_decision shows WaitingForEvents)
  6. Resume approval_gate via owner endpoint
  7. Verify flow completes with success=True and decision='approved'

Windmill suspend state convention (v1.390.0):
  Module M with suspend → flow shows M: Success and M+1: WaitingForEvents.
  "approval_gate: WaitingForEvents" = review_gate's suspend is active.
  "record_decision: WaitingForEvents" = approval_gate's suspend is active.
"""
import json
import os
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WM_BASE = os.environ.get("WINDMILL_BASE_URL", "http://localhost:8100")
# Fallback token is a dev-machine placeholder; the runtime env var wins.
WM_TOKEN = os.environ.get("WINDMILL_TOKEN", "dRRYLqFTy6XzvstQ3iEVzeVQ1jwQTXQd")
WS = os.environ.get("WINDMILL_WORKSPACE", "capital-call")
# Full flow path including folder prefix
FLOW_PATH = "f/approval/capital_call_approval"


def api(method: str, path: str, body: dict | None = None):
    url = f"{WM_BASE}{path}"
    headers = {"Authorization": f"Bearer {WM_TOKEN}", "Content-Type": "application/json"}
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
    except HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"  HTTP {e.code}: {body_text[:300]}")
        raise
    except URLError as e:
        print(f"  Connection error: {e.reason}")
        raise


def wait_for_module_type(
    job_id: str,
    module_id: str,
    target_types: set[str],
    timeout: int = 30,
) -> dict:
    """Poll until named module reaches one of target_types; return full job status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = api("GET", f"/api/w/{WS}/jobs_u/get/{job_id}")
        if status.get("type") == "CompletedJob":
            return status
        for mod in status.get("flow_status", {}).get("modules", []):
            if mod["id"] == module_id and mod.get("type") in target_types:
                print(f"  Module {module_id}: {mod.get('type')}")
                return status
        time.sleep(2)
    raise TimeoutError(
        f"Module {module_id!r} did not reach {target_types} within {timeout}s"
    )


def wait_for_completion(job_id: str, timeout: int = 30) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = api("GET", f"/api/w/{WS}/jobs_u/get/{job_id}")
        if status.get("type") == "CompletedJob":
            return status
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def resume_flow(job_id: str, payload: dict) -> None:
    """Resume a suspended flow as owner (no HMAC signature required)."""
    result = api("POST", f"/api/w/{WS}/jobs/flow/resume/{job_id}", payload)
    # 201 returns empty body (None); any other value is also fine
    assert result is None or isinstance(result, (str, dict)), (
        f"Unexpected resume response: {result!r}"
    )


def print_modules(status: dict) -> None:
    for mod in status.get("flow_status", {}).get("modules", []):
        print(f"    {mod['id']}: {mod.get('type','?')}")


def main() -> None:
    print("=" * 60)
    print("Windmill E2E Test: Capital Call Approval Flow (Full Path)")
    print("=" * 60)

    # Step 0: Verify Windmill is up
    print("\n[0] Checking Windmill...")
    api("GET", "/api/version")
    print("  Windmill: OK")

    # Step 1: Verify flow exists
    print("\n[1] Checking flow exists...")
    flow = api("GET", f"/api/w/{WS}/flows/get/{FLOW_PATH}")
    print(f"  Flow: {flow['summary']}")
    module_ids = [m["id"] for m in flow["value"]["modules"]]
    print(f"  Modules: {module_ids}")
    assert module_ids == [
        "receive_package", "classify_document", "review_gate",
        "approval_gate", "record_decision",
    ], f"Unexpected modules: {module_ids}"

    # Step 2: Start the flow
    print("\n[2] Starting flow...")
    package_id = f"e2e-{uuid.uuid4().hex[:8]}"
    # Windmill run endpoint: /jobs/run/f/{path} where {path} includes folder prefix
    job_id = api(
        "POST",
        f"/api/w/{WS}/jobs/run/f/{FLOW_PATH}",
        {"package_id": package_id, "uploaded_by": "e2e-test"},
    )
    assert isinstance(job_id, str) and len(job_id) > 0, (
        f"Expected string job_id, got: {job_id!r}"
    )
    print(f"  Job ID: {job_id}")
    print(f"  Package: {package_id}")

    # Step 3: Wait for review_gate suspend
    # Windmill shows the NEXT module as WaitingForEvents when a suspend is active.
    # review_gate suspend → approval_gate shows WaitingForEvents
    print("\n[3] Waiting for review_gate to suspend...")
    status = wait_for_module_type(job_id, "approval_gate", {"WaitingForEvents"}, timeout=30)
    print("  Module states:")
    print_modules(status)
    modules = {m["id"]: m for m in status["flow_status"]["modules"]}
    assert modules["review_gate"]["type"] == "Success", (
        "review_gate must be Success (identity ran) when its suspend is active"
    )
    assert modules["approval_gate"]["type"] == "WaitingForEvents"

    # Step 4: Resume review_gate
    print("\n[4] Resuming review_gate (first gate)...")
    resume_flow(job_id, {"approved": True, "note": "LGTM — proceeding to attestation"})
    print("  Resume sent")

    # Step 5: Wait for approval_gate suspend
    # approval_gate suspend → record_decision shows WaitingForEvents
    print("\n[5] Waiting for approval_gate to suspend...")
    status = wait_for_module_type(job_id, "record_decision", {"WaitingForEvents"}, timeout=30)
    print("  Module states:")
    print_modules(status)
    modules = {m["id"]: m for m in status["flow_status"]["modules"]}
    assert modules["approval_gate"]["type"] == "Success", (
        "approval_gate must be Success (identity ran) when its suspend is active"
    )
    assert modules["record_decision"]["type"] == "WaitingForEvents"

    # Step 6: Resume approval_gate
    print("\n[6] Resuming approval_gate (second gate)...")
    resume_flow(job_id, {"approved": True, "note": "Formally attested"})
    print("  Resume sent")

    # Step 7: Wait for flow completion
    print("\n[7] Waiting for flow to complete...")
    final = wait_for_completion(job_id, timeout=30)
    print("  Module states:")
    print_modules(final)

    print("\n" + "=" * 60)
    print("E2E Test Results")
    print("=" * 60)
    print(f"Flow path:  {FLOW_PATH}")
    print(f"Job ID:     {job_id}")
    print(f"Package:    {package_id}")
    print(f"Type:       {final.get('type')}")
    print(f"Success:    {final.get('success')}")

    result = final.get("result", {})
    print(f"Decision:   {result.get('decision')}")
    print(f"Recorded:   {result.get('recorded')}")
    print(f"Message:    {result.get('message')}")

    assert final.get("success") is True, (
        f"Flow failed: {final.get('result')}"
    )
    assert result.get("decision") == "approved", (
        f"Expected decision='approved', got: {result.get('decision')!r}"
    )
    assert result.get("recorded") is True
    assert result.get("package_id") == package_id

    print("\nAll assertions passed — E2E PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}")
        sys.exit(1)
    except TimeoutError as e:
        print(f"\nTIMEOUT: {e}")
        sys.exit(1)
    except (HTTPError, URLError) as e:
        print(f"\nHTTP ERROR: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""Test that monitoring endpoints work and return expected data."""
import json
import os
import sys
from urllib.request import Request, urlopen

BACKEND = os.environ.get("BACKEND_URL", "https://arukai-capital-call-backend-staging-1035777337524.europe-west4.run.app")

def check(name, url, expect_status=200, check_fn=None):
    try:
        req = Request(url)
        resp = urlopen(req, timeout=10)
        status = resp.status
        body = resp.read().decode()
        ok = status == expect_status
        if check_fn and ok:
            ok = check_fn(body)
        print(f"  {'PASS' if ok else 'FAIL'} {name} (HTTP {status})")
        return ok
    except Exception as e:
        print(f"  FAIL {name} ({e})")
        return False

def main():
    print("Monitoring verification\n")

    results = []
    results.append(check("Health endpoint", f"{BACKEND}/health",
                         check_fn=lambda b: '"ok"' in b))

    results.append(check("Metrics endpoint", f"{BACKEND}/metrics",
                         check_fn=lambda b: "request_total" in b or "uptime_seconds" in b))

    # Health detailed requires auth — test that it rejects without token
    results.append(check("Health detailed (no auth)", f"{BACKEND}/health/detailed",
                         expect_status=401))

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()

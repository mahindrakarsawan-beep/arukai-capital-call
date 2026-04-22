"""TDD gate for the standalone scripts/contract_check.py CLI.

Scope: verify the standalone contract checker (Miller's Rule 15 §4 evidence
source) exists, runs, and emits the governance-required output section.

Not a replacement for test_api_contract.py — that test remains the primary
correctness gate for every frontend↔backend path+method pair. This test only
gates the CLI wrapper contract (filename + exit code + header).
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "contract_check.py"


def _run_script():
    env = os.environ.copy()
    env.setdefault("APP_ENV", "test")
    env.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    env.setdefault("JWT_SECRET", "test-secret-for-contract-check")
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT / "backend"),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def test_contract_check_script_exists():
    assert SCRIPT.exists(), (
        f"scripts/contract_check.py not found at {SCRIPT} — Miller's Rule 15 "
        "§4 evidence source is missing"
    )


def test_contract_check_script_exits_zero_on_green_contract():
    result = _run_script()
    assert result.returncode == 0, (
        f"contract_check.py exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_contract_check_script_prints_rule15_header():
    result = _run_script()
    combined = result.stdout + result.stderr
    assert "RULE 15" in combined, (
        "governance header missing from contract_check.py output — "
        "Miller's §4 evidence section requires the literal string 'RULE 15'.\n"
        f"output:\n{combined}"
    )


def test_contract_check_script_reports_counts():
    """Output must include a summary line with the counts so Miller can paste
    it into the H9 §4 evidence block without grepping."""
    result = _run_script()
    combined = result.stdout + result.stderr
    assert "frontend calls" in combined.lower(), (
        f"summary line missing 'frontend calls' count.\noutput:\n{combined}"
    )
    assert "backend routes" in combined.lower(), (
        f"summary line missing 'backend routes' count.\noutput:\n{combined}"
    )

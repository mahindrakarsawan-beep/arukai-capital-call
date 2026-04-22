"""
POR-158: Contract test — Cloud Run deploy workflow secrets injection.

Parses .github/workflows/cloud-run-deploy.yml and asserts that all required
secrets and env vars are present in the backend deploy step.  Tests are
intentionally strict: a missing key is a silent runtime failure, not a warning.
"""

import pathlib

import pytest
import yaml

WORKFLOW_PATH = (
    pathlib.Path(__file__).parents[2]
    / ".github"
    / "workflows"
    / "cloud-run-deploy.yml"
)

# Secrets that must appear in the backend Cloud Run deploy step.
REQUIRED_SECRETS = [
    "DATABASE_URL",
    "JWT_SECRET",
    "ANTHROPIC_API_KEY",
    # POR-158 additions — these were missing and caused silent empty-string fallback
    "MISTRAL_API_KEY",
    "WINDMILL_TOKEN",
]

# Config values injected as env_vars (not GCP secrets) in the backend step.
REQUIRED_ENV_VARS = [
    "BACKUP_GCS_BUCKET",
]


def _load_workflow() -> dict:
    with WORKFLOW_PATH.open() as fh:
        return yaml.safe_load(fh)


def _backend_deploy_step(workflow: dict) -> dict:
    """Return the deploy-cloudrun step that targets the backend service."""
    steps = workflow["jobs"]["deploy"]["steps"]
    for step in steps:
        step_name = step.get("name", "")
        uses = step.get("uses", "")
        if "backend" in step_name.lower() and "deploy-cloudrun" in uses:
            return step
    raise AssertionError(
        "Could not locate backend Cloud Run deploy step in workflow. "
        "Expected a step with 'backend' in its name and uses: google-github-actions/deploy-cloudrun."
    )


def _parse_block(raw: str) -> set[str]:
    """Parse a multiline key=value block (secrets: or env_vars:) into a set of keys."""
    keys: set[str] = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        key = line.split("=")[0].strip()
        if key:
            keys.add(key)
    return keys


class TestDeployWorkflowContract:
    def setup_method(self):
        self.workflow = _load_workflow()
        self.step = _backend_deploy_step(self.workflow)

    def test_workflow_file_parseable(self):
        """Workflow YAML must parse without error."""
        assert self.workflow is not None

    def test_backend_deploy_step_found(self):
        """Backend deploy step must exist."""
        assert self.step is not None

    @pytest.mark.parametrize("secret_key", REQUIRED_SECRETS)
    def test_secret_present_in_backend_step(self, secret_key: str):
        """Each required secret must appear in the backend step secrets block."""
        raw_secrets = self.step.get("with", {}).get("secrets", "") or ""
        injected = _parse_block(raw_secrets)
        assert secret_key in injected, (
            f"Secret '{secret_key}' is missing from the backend Cloud Run deploy step. "
            f"Present secrets: {sorted(injected)}"
        )

    @pytest.mark.parametrize("env_key", REQUIRED_ENV_VARS)
    def test_env_var_present_in_backend_step(self, env_key: str):
        """Each required env var must appear in the backend step env_vars block."""
        raw_env = self.step.get("with", {}).get("env_vars", "") or ""
        injected = _parse_block(raw_env)
        assert env_key in injected, (
            f"Env var '{env_key}' is missing from the backend Cloud Run deploy step. "
            f"Present env_vars: {sorted(injected)}"
        )

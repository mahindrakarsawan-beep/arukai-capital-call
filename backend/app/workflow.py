"""Workflow manager — Windmill if configured, custom state machine as fallback."""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Routes workflow operations to Windmill or custom state machine."""

    def __init__(self):
        self._windmill = None

    @property
    def uses_windmill(self) -> bool:
        from app.windmill_client import windmill
        return windmill.is_configured()

    def start_flow(self, package_id: str, uploaded_by: str) -> Optional[str]:
        if self.uses_windmill:
            from app.windmill_client import windmill
            run_id = windmill.start_flow(
                "f/capital-call-approval",
                {"package_id": package_id, "uploaded_by": uploaded_by}
            )
            if run_id:
                logger.info("Windmill flow started: %s for package %s", run_id, package_id)
                return run_id
            logger.warning("Windmill flow start failed — using custom state machine")
        return None  # caller uses custom state machine

    def complete_review(self, package_id: str, run_id: Optional[str],
                        approved: bool, note: str) -> bool:
        if run_id and self.uses_windmill:
            from app.windmill_client import windmill
            windmill.complete_approval(run_id, approved, note)
            logger.info("Windmill review completed: %s approved=%s", run_id, approved)
            return True
        return False  # caller uses custom state machine

    def complete_attestation(self, package_id: str, run_id: Optional[str],
                             approved: bool, note: str) -> bool:
        if run_id and self.uses_windmill:
            from app.windmill_client import windmill
            windmill.complete_approval(run_id, approved, note)
            logger.info("Windmill attestation completed: %s approved=%s", run_id, approved)
            return True
        return False

    def get_status(self, run_id: Optional[str]) -> Optional[dict]:
        if run_id and self.uses_windmill:
            from app.windmill_client import windmill
            return windmill.get_run_status(run_id)
        return None


workflow = WorkflowManager()

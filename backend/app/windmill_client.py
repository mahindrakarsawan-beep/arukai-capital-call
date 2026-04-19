"""Thin Windmill API client — delegates workflow execution. No SDK dependency."""
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class WindmillClient:
    def __init__(self, base_url=None, token=None):
        self.base_url = (base_url or os.getenv("WINDMILL_BASE_URL", "")).rstrip("/")
        self.token = token or os.getenv("WINDMILL_TOKEN", "")
        self.workspace = os.getenv("WINDMILL_WORKSPACE", "capital-call")

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _request(self, method: str, path: str, body: dict = None):
        if not self.is_configured():
            return None
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        try:
            req = Request(url, method=method, headers=headers)
            if body:
                req.data = json.dumps(body).encode()
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.error("Windmill %s %s failed: %s", method, path, e)
            return None

    def start_flow(self, flow_path: str, args: dict) -> str | None:
        r = self._request("POST", f"/api/w/{self.workspace}/jobs/run/f/{flow_path}", {"args": args})
        return r if isinstance(r, str) else (r.get("id") if isinstance(r, dict) else None)

    def get_run_status(self, run_id: str) -> dict | None:
        return self._request("GET", f"/api/w/{self.workspace}/jobs_u/get/{run_id}")

    def complete_approval(self, run_id: str, approved: bool, note: str) -> None:
        self._request("POST", f"/api/w/{self.workspace}/jobs_u/resume/{run_id}",
                       {"approved": approved, "note": note})

    def list_pending_approvals(self) -> list[dict]:
        r = self._request("GET", f"/api/w/{self.workspace}/jobs/list?is_suspended=true")
        return r if isinstance(r, list) else []


# Module-level singleton
windmill = WindmillClient()

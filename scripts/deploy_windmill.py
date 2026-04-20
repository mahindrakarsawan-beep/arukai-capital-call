#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
import argparse

# Constants
RECEIVE_PACKAGE_BODY = '''
from datetime import datetime, timezone

def main(package_id: str, uploaded_by: str) -> dict:
    return {
        "package_id": package_id,
        "uploaded_by": uploaded_by,
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
'''

CLASSIFY_DOCUMENT_BODY = '''
def main(package_id: str, received_at: str) -> dict:
    return {
        "package_id": package_id,
        "classification": "capital_call_notice",
        "confidence": 0.99,
        "extracted_fields": {"amount_usd": 2500000, "due_date": "2026-05-15"},
    }
'''

RECORD_DECISION_BODY = '''
from datetime import datetime, timezone

def main(package_id: str, approved: bool, note: str) -> dict:
    return {
        "package_id": package_id,
        "decision": "approved" if approved else "rejected",
        "note": note,
        "recorded": True,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
'''

RECEIVE_SCHEMA = {"type": "object", "properties": {"package_id": {"type": "string"}, "uploaded_by": {"type": "string"}}, "required": ["package_id", "uploaded_by"]}
CLASSIFY_SCHEMA = {"type": "object", "properties": {"package_id": {"type": "string"}, "received_at": {"type": "string"}}, "required": ["package_id", "received_at"]}
RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "package_id": {"type": "string"},
        "approved": {"type": "boolean"},
        "note": {"type": "string"},
    },
    "required": ["package_id", "approved", "note"],
}

def http(method, path, body=None, token=None):
    base_url = os.getenv("WINDMILL_BASE_URL", "http://localhost:8100")
    url = f"{base_url}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw if raw else None
            return (response.code, parsed)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw if raw else None
        return (e.code, parsed)
    except urllib.error.URLError as e:
        raise Exception(f"Connection error: {str(e)}")

def ensure_workspace(token):
    workspace_id = os.getenv("WINDMILL_WORKSPACE", "capital-call")
    body = {
        "id": workspace_id,
        "name": "Capital Call",
        # Windmill 1.390 creates the owner username automatically from the
        # authenticated user; passing username here returns 400.
    }
    status, response = http("POST", "/api/workspaces/create", body=body, token=token)

    # 409 = already exists (idempotent). 2xx = created. Anything else is a real error.
    if status == 409 or "already exists" in str(response).lower():
        return
    if status not in (200, 201):
        raise Exception(f"Workspace creation failed: HTTP {status}: {response}")

def ensure_script(token, name, content, schema):
    workspace_id = os.getenv("WINDMILL_WORKSPACE", "capital-call")
    path = f"/api/w/{workspace_id}/scripts/get/f/scripts/{name}"
    status, response = http("GET", path, token=token)

    parent_hash = None
    if status == 200:
        parent_hash = response["hash"]

    script_path = f"f/scripts/{name}"
    body = {
        "path": script_path,
        "summary": f"{name} script for capital-call flow",
        "description": "Auto-deployed by scripts/deploy_windmill.py",
        "content": content,
        "language": "python3",
        "schema": schema,
        "is_template": False,
        "kind": "script",
    }

    if parent_hash is not None:
        body["parent_hash"] = parent_hash

    create_path = f"/api/w/{workspace_id}/scripts/create"
    status, response = http("POST", create_path, body=body, token=token)

    # Windmill returns 400 "same hash already exists" when content hasn't changed —
    # that's the idempotent-success case for us (script already deployed at this version).
    if status == 400 and "same hash" in str(response).lower():
        return
    if status not in (200, 201):
        raise Exception(f"Script deployment failed: HTTP {status}: {response}")

def ensure_flow(token):
    workspace_id = os.getenv("WINDMILL_WORKSPACE", "capital-call")
    flow_path = Path(__file__).resolve().parent.parent / "backend/windmill_flows/capital_call_approval.json"

    try:
        with open(flow_path, 'r') as f:
            flow_data = json.load(f)
    except Exception as e:
        raise Exception(f"Failed to read flow file: {str(e)}")

    # Check if flow exists
    check_path = f"/api/w/{workspace_id}/flows/get/f/approval/capital_call_approval"
    status, _ = http("GET", check_path, token=token)

    # Prepare flow body
    body = {
        "path": "f/approval/capital_call_approval",
        "summary": flow_data.get("summary", "Capital Call Approval"),
        "description": flow_data.get("description", ""),
        "value": flow_data["value"],
        "schema": flow_data.get("schema", {}),
    }

    # Determine if we're creating or updating
    # Windmill 1.390: update endpoint requires the flow path in the URL:
    #   POST /api/w/{ws}/flows/update/{path}
    # create endpoint rejects duplicates with 400 "already exists".
    if status == 200:
        update_path = f"/api/w/{workspace_id}/flows/update/f/approval/capital_call_approval"
        status, response = http("POST", update_path, body=body, token=token)
    else:
        create_path = f"/api/w/{workspace_id}/flows/create"
        status, response = http("POST", create_path, body=body, token=token)

    if status == 400 and "already exists" in str(response).lower():
        return  # idempotent
    if status not in (200, 201):
        raise Exception(f"Flow deployment failed: HTTP {status}: {response}")

def main():
    parser = argparse.ArgumentParser(description='Deploy Windmill workflows')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    try:
        token = os.getenv("WINDMILL_TOKEN")
        if not token:
            email = os.getenv("WINDMILL_EMAIL", "admin@windmill.dev")
            password = os.getenv("WINDMILL_PASSWORD", "changeme")
            status, response = http("POST", "/api/auth/login", body={"email": email, "password": password})
            if status != 200:
                raise Exception(f"Login failed: HTTP {status}: {response}")
            token = response.strip('"')

        ensure_workspace(token)
        ensure_script(token, "receive_package", RECEIVE_PACKAGE_BODY, RECEIVE_SCHEMA)
        ensure_script(token, "classify_document", CLASSIFY_DOCUMENT_BODY, CLASSIFY_SCHEMA)
        ensure_script(token, "record_decision", RECORD_DECISION_BODY, RECORD_SCHEMA)
        ensure_flow(token)

        print(f"workspace: {os.getenv('WINDMILL_WORKSPACE', 'capital-call')}")
        print(f"flow_url: {os.getenv('WINDMILL_BASE_URL', 'http://localhost:8100')}/{os.getenv('WINDMILL_WORKSPACE', 'capital-call')}/flows/get/f/approval/capital_call_approval")
        print(f"token: {token}")

    except Exception as e:
        if args.debug:
            raise
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

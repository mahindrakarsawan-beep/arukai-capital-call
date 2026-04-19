"""TDD tests for OIDC integration — written BEFORE implementation."""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


def test_oidc_authorize_returns_501_when_not_configured(client):
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OIDC_ISSUER_URL", None)
        resp = client.get("/auth/oidc/authorize")
        assert resp.status_code == 501
        assert "not configured" in resp.json()["detail"].lower()


def test_oidc_callback_returns_501_when_not_configured(client):
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OIDC_ISSUER_URL", None)
        resp = client.post("/auth/oidc/callback", json={"code": "test"})
        assert resp.status_code == 501


def test_oidc_callback_rejects_missing_code(client):
    with patch.dict(os.environ, {
        "OIDC_ISSUER_URL": "https://idp.example.com",
        "OIDC_CLIENT_ID": "test",
        "OIDC_CLIENT_SECRET": "secret",
        "OIDC_REDIRECT_URI": "https://app.example.com/callback",
    }):
        resp = client.post("/auth/oidc/callback", json={})
        assert resp.status_code in (400, 422)


def test_oidc_role_mapping_defaults_to_reviewer():
    from app.routers.auth import _map_oidc_role
    assert _map_oidc_role({}) == "reviewer"
    assert _map_oidc_role({"groups": ["unknown"]}) == "reviewer"


def test_oidc_role_mapping_extracts_valid_roles():
    from app.routers.auth import _map_oidc_role
    assert _map_oidc_role({"groups": ["admin"]}) == "admin"
    assert _map_oidc_role({"roles": ["approver"]}) == "approver"
    assert _map_oidc_role({"groups": ["reviewer"]}) == "reviewer"


def test_oidc_role_mapping_groups_over_roles():
    from app.routers.auth import _map_oidc_role
    assert _map_oidc_role({"groups": ["admin"], "roles": ["reviewer"]}) == "admin"

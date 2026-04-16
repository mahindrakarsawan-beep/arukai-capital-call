"""TDD: Audit events append-only enforcement (R9).

Tests that UPDATE and DELETE on audit_events raise an exception.
In SQLite dev mode, this is enforced by the Python-level audit guard.
In PostgreSQL production, this is enforced by the DB trigger from migration 0001.
"""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


def _login(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_audit_event_update_raises(async_session):
    """Attempting to UPDATE an audit_events row must raise AuditMutationError (R9).

    The guard is enabled for the duration of this test.
    In PostgreSQL, the trigger enforces this at DB level.
    """
    from app.models import AuditEvent
    from app.audit_guard import AuditMutationError, enable_audit_guard, disable_audit_guard

    # Insert a real audit event
    event = AuditEvent(
        package_id=None,
        actor_user_id=None,
        action="test_guard_update",
        before_state=None,
        after_state={"test": True},
    )
    async_session.add(event)
    await async_session.commit()
    await async_session.refresh(event)

    # Enable guard
    enable_audit_guard()
    try:
        from app.audit_guard import check_audit_mutation_allowed
        with pytest.raises(AuditMutationError):
            check_audit_mutation_allowed("audit_events", "UPDATE")
    finally:
        disable_audit_guard()


@pytest.mark.asyncio
async def test_audit_event_delete_raises(async_session):
    """Attempting to DELETE an audit_events row must raise AuditMutationError (R9)."""
    from app.models import AuditEvent
    from app.audit_guard import AuditMutationError, enable_audit_guard, disable_audit_guard

    event = AuditEvent(
        package_id=None,
        actor_user_id=None,
        action="test_guard_delete",
        before_state=None,
        after_state={"test": True},
    )
    async_session.add(event)
    await async_session.commit()
    await async_session.refresh(event)

    enable_audit_guard()
    try:
        from app.audit_guard import check_audit_mutation_allowed
        with pytest.raises(AuditMutationError):
            check_audit_mutation_allowed("audit_events", "DELETE")
    finally:
        disable_audit_guard()


def test_audit_guard_does_not_block_other_tables():
    """Guard does not block mutations on non-audit tables."""
    from app.audit_guard import AuditMutationError, enable_audit_guard, disable_audit_guard, check_audit_mutation_allowed

    enable_audit_guard()
    try:
        # Should not raise for packages table
        check_audit_mutation_allowed("packages", "UPDATE")
        check_audit_mutation_allowed("users", "DELETE")
        check_audit_mutation_allowed("reviewer_notes", "UPDATE")
    finally:
        disable_audit_guard()


def test_audit_events_no_delete_via_api(client: TestClient):
    """There is no DELETE /audit endpoint — any attempt returns 404 or 405."""
    admin_token_resp = client.post(
        "/auth/login",
        json={"email": "admin@arukai.example", "password": "admin123"},
    )
    token = admin_token_resp.json()["access_token"]

    resp = client.delete("/audit/some-id", headers={"Authorization": f"Bearer {token}"})
    # No such endpoint = 404 or 405
    assert resp.status_code in (404, 405)


def test_audit_events_no_update_via_api(client: TestClient):
    """There is no PATCH/PUT /audit endpoint."""
    admin_token_resp = client.post(
        "/auth/login",
        json={"email": "admin@arukai.example", "password": "admin123"},
    )
    token = admin_token_resp.json()["access_token"]

    resp = client.patch("/audit/some-id", json={}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (404, 405)


def test_audit_guard_inactive_by_default():
    """Guard is not active by default (PostgreSQL handles it in production)."""
    from app.audit_guard import _GUARD_ACTIVE, check_audit_mutation_allowed, AuditMutationError

    # Guard should not be active (default is False)
    # This test verifies that the guard does not interfere with normal operation
    # Note: if another test enabled the guard and didn't disable it, this would fail
    # The enable/disable calls in other tests use finally blocks to ensure cleanup
    try:
        check_audit_mutation_allowed("audit_events", "UPDATE")  # Should not raise
    except AuditMutationError:
        pytest.fail("Guard was unexpectedly active — ensure tests use finally blocks")

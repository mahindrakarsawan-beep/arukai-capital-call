"""SQLite-level append-only guard for audit_events (R9).

PostgreSQL uses a BEFORE UPDATE OR DELETE trigger (created in migration 0001).
For SQLite dev / test environments, this module provides a Python-level guard
that can be activated in test scenarios.

The guard is NOT automatically active in production (PostgreSQL handles it).
To activate in tests, call install_audit_guard() after creating the engine.
"""
from typing import Optional


class AuditMutationError(Exception):
    """Raised when UPDATE or DELETE is attempted on audit_events (R9)."""


# Global flag — set to True in test environments that want the guard active
_GUARD_ACTIVE = False


def enable_audit_guard():
    """Enable the Python-level audit guard (for test use)."""
    global _GUARD_ACTIVE
    _GUARD_ACTIVE = True


def disable_audit_guard():
    """Disable the Python-level audit guard."""
    global _GUARD_ACTIVE
    _GUARD_ACTIVE = False


def check_audit_mutation_allowed(table_name: str, operation: str) -> None:
    """Check if a mutation on audit_events is allowed.

    Raises AuditMutationError if the guard is active and the operation is
    UPDATE or DELETE on audit_events.
    """
    if not _GUARD_ACTIVE:
        return
    if table_name and table_name.lower() == "audit_events":
        if operation.upper() in ("UPDATE", "DELETE"):
            raise AuditMutationError("audit_events is append-only")
